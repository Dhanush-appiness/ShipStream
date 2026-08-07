from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from organizations.models import Membership, Organization
from projects.models import Project, ProjectMember
from tasks.models import ActivityLog, Comment, Label, Notification, Task, TaskLabel

SEED_PASSWORD='password123'


class Command(BaseCommand):
    help='Seed the database with demo organizations, users, projects and tasks.'

    def add_arguments(self,parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Delete existing seed data (matched by email/slug) before reseeding.',
        )

    def handle(self,*args,**options):
        if options['flush']:
            self.flush_seed_data()

        with transaction.atomic():
            organizations=self.seed_organizations()
            users=self.seed_users()
            memberships=self.seed_memberships(organizations,users)
            projects=self.seed_projects(organizations)
            self.seed_project_members(projects,memberships)
            labels=self.seed_labels(organizations)
            tasks=self.seed_tasks(projects,users)
            self.seed_labels_on_tasks(tasks,labels)
            self.seed_comment_with_mention(tasks,users)

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(organizations)} organizations, {len(users)} users, '
            f'{len(projects)} projects, {len(tasks)} tasks.'
        ))

    def flush_seed_data(self):
        User.objects.filter(email__in=SEED_USER_EMAILS).delete()
        Organization.objects.filter(slug__in=SEED_ORG_SLUGS).delete()
        self.stdout.write(self.style.WARNING('Existing seed data removed.'))

    def seed_organizations(self):
        organizations={}
        for slug,name,plan in [
            ('acme-corp','Acme Corp','pro'),
            ('globex-inc','Globex Inc','free'),
        ]:
            organization,_=Organization.objects.get_or_create(
                slug=slug,
                defaults={'name':name,'plan':plan},
            )
            organizations[slug]=organization
        return organizations

    def seed_users(self):
        users={}
        for email,first_name,last_name in [
            ('alice@example.com','Alice','Owens'),
            ('bob@example.com','Bob','Bridges'),
            ('carol@example.com','Carol','Chen'),
            ('dave@example.com','Dave','Diaz'),
            ('erin@example.com','Erin','Ellis'),
        ]:
            user=User.objects.filter(email=email).first()
            if user is None:
                user=User.objects.create_user(
                    email=email,
                    password=SEED_PASSWORD,
                    first_name=first_name,
                    last_name=last_name,
                    is_verified=True,
                )
            users[email]=user
        return users

    def seed_memberships(self,organizations,users):
        acme=organizations['acme-corp']
        globex=organizations['globex-inc']
        rows=[
            (users['alice@example.com'],acme,Membership.RoleChoices.OWNER),
            (users['bob@example.com'],acme,Membership.RoleChoices.ADMIN),
            (users['bob@example.com'],globex,Membership.RoleChoices.MEMBER),
            (users['carol@example.com'],acme,Membership.RoleChoices.MEMBER),
            (users['dave@example.com'],acme,Membership.RoleChoices.GUEST),
            (users['erin@example.com'],globex,Membership.RoleChoices.OWNER),
        ]
        memberships=[]
        for user,organization,role in rows:
            membership,_=Membership.objects.get_or_create(
                user=user,
                organization=organization,
                defaults={'role':role},
            )
            memberships.append(membership)
        return memberships

    def seed_projects(self,organizations):
        acme=organizations['acme-corp']
        globex=organizations['globex-inc']
        specs=[
            (acme,'Website Relaunch','Rebuild the marketing site on the new design system.'),
            (acme,'Mobile App','Native iOS/Android client for existing API.'),
            (globex,'Data Migration','Move legacy warehouse data into the new pipeline.'),
        ]
        projects=[]
        for organization,name,description in specs:
            project,_=Project.objects.get_or_create(
                organization=organization,
                name=name,
                defaults={'description':description,'status':'ACTIVE'},
            )
            projects.append(project)
        return projects

    def seed_project_members(self,projects,memberships):
        by_org:dict[int,list]={}
        for membership in memberships:
            by_org.setdefault(membership.organization_id,[]).append(membership.user)

        for project in projects:
            for user in by_org.get(project.organization_id,[]):
                ProjectMember.objects.get_or_create(
                    project=project,
                    user=user,
                )

    def seed_labels(self,organizations):
        labels={}
        for slug,name,color in [
            ('acme-corp','Bug','#e74c3c'),
            ('acme-corp','Feature','#2ecc71'),
            ('acme-corp','Urgent','#f39c12'),
            ('globex-inc','Bug','#e74c3c'),
            ('globex-inc','Feature','#2ecc71'),
        ]:
            organization=organizations[slug]
            label,_=Label.objects.get_or_create(
                organization=organization,
                name=name,
                defaults={'color':color},
            )
            labels[(slug,name)]=label
        return labels

    def seed_tasks(self,projects,users):
        today=timezone.localdate()
        alice=users['alice@example.com']
        bob=users['bob@example.com']
        carol=users['carol@example.com']
        dave=users['dave@example.com']
        erin=users['erin@example.com']

        website,mobile,migration=projects

        specs=[
            (website,'Set up design tokens',alice,'DONE','HIGH',today-timedelta(days=10)),
            (website,'Build homepage hero section',bob,'IN_PROGRESS','HIGH',today+timedelta(days=3)),
            (website,'Fix broken nav on mobile',carol,'BLOCKED','MEDIUM',today-timedelta(days=2)),
            (website,'Write launch announcement copy',dave,'TODO','LOW',today+timedelta(days=14)),
            (mobile,'Wire up auth screens',bob,'IN_PROGRESS','HIGH',today+timedelta(days=5)),
            (mobile,'Push notification integration',alice,'TODO','MEDIUM',None),
            (migration,'Audit legacy schema',erin,'DONE','HIGH',today-timedelta(days=20)),
            (migration,'Write transform scripts',erin,'IN_PROGRESS','HIGH',today-timedelta(days=1)),
            (migration,'Validate row counts post-migration',bob,'TODO','MEDIUM',today+timedelta(days=7)),
        ]

        tasks=[]
        position_by_column:dict[tuple[int,str],int]={}
        for project,title,assignee,status,priority,due_date in specs:
            key=(project.id,status)
            position=position_by_column.get(key,0)
            task,created=Task.objects.get_or_create(
                project=project,
                title=title,
                defaults={
                    'description':f'{title} for {project.name}.',
                    'assignee':assignee,
                    'created_by':assignee,
                    'status':status,
                    'priority':priority,
                    'due_date':due_date,
                    'position':position,
                },
            )
            if created:
                position_by_column[key]=position+1
                ActivityLog.objects.create(
                    organization=project.organization,
                    task=task,
                    actor=assignee,
                    action='TASK_CREATED',
                    payload={'seed':True},
                )
            tasks.append(task)
        return tasks

    def seed_labels_on_tasks(self,tasks,labels):
        pairs=[
            (tasks[2],('acme-corp','Bug')),
            (tasks[1],('acme-corp','Feature')),
            (tasks[2],('acme-corp','Urgent')),
            (tasks[7],('globex-inc','Bug')),
        ]
        for task,label_key in pairs:
            label=labels.get(label_key)
            if label is None:
                continue
            TaskLabel.objects.get_or_create(task=task,label=label)

    def seed_comment_with_mention(self,tasks,users):
        task=tasks[2]
        author=users['carol@example.com']
        mentioned=users['bob@example.com']
        comment,created=Comment.objects.get_or_create(
            task=task,
            author=author,
            content=f'@{mentioned.email} can you take a look at this, it is blocking the release.',
        )
        if created:
            ActivityLog.objects.create(
                organization=task.project.organization,
                task=task,
                actor=author,
                action='COMMENT_ADDED',
                payload={'seed':True},
            )
            Notification.objects.get_or_create(
                user=mentioned,
                task=task,
                type='MENTION',
                defaults={
                    'title':'You were mentioned in a comment',
                    'body':f"{author.email} mentioned you in '{task.title}'.",
                },
            )


SEED_USER_EMAILS=[
    'alice@example.com',
    'bob@example.com',
    'carol@example.com',
    'dave@example.com',
    'erin@example.com',
]

SEED_ORG_SLUGS=[
    'acme-corp',
    'globex-inc',
]
