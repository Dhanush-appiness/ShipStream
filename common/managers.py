from django.db import models


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        return self.update(is_deleted=True)

    def hard_delete(self):
        return super().delete()

    def deleted(self):
        return self.filter(is_deleted=True)


class ProjectQuerySet(SoftDeleteQuerySet):
    def for_organization(self,organization):
        return self.filter(
            organization=organization
        )


class TaskQuerySet(SoftDeleteQuerySet):
    def for_organization(self,organization):
        return self.filter(
            project__organization=organization
        )


class ProjectManager(models.Manager):
    def get_queryset(self):
        return ProjectQuerySet(
            self.model,
            using=self._db
        ).filter(is_deleted=False)

    def for_organization(self,organization):
        return self.get_queryset().for_organization(
            organization
        )


class TaskManager(models.Manager):
    def get_queryset(self):
        return TaskQuerySet(
            self.model,
            using=self._db
        ).filter(is_deleted=False)

    def for_organization(self,organization):
        return self.get_queryset().for_organization(
            organization
        )


class AllObjectsManager(models.Manager):
    pass
