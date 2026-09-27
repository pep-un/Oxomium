from django.db import transaction

from conformity.models import Attachment


def attachment_has_relations(attachment):
    """Return whether an attachment is still referenced by any M2M owner."""
    return any(
        getattr(attachment, relation.get_accessor_name()).exists()
        for relation in attachment._meta.related_objects
        if relation.many_to_many
    )


@transaction.atomic
def unlink_attachment(owner, attachment):
    """Remove one owner relation and delete the attachment if it becomes orphaned."""
    field = owner._meta.get_field("attachment")
    if not field.many_to_many or field.remote_field.model is not Attachment:
        raise ValueError("Owner does not expose an Attachment M2M relation.")

    relation = owner.attachment
    if not relation.filter(pk=attachment.pk).exists():
        raise ValueError("Attachment is not linked to this object.")

    relation.remove(attachment)
    if attachment_has_relations(attachment):
        return False

    storage = attachment.file.storage
    file_name = attachment.file.name
    attachment.delete()
    if file_name:
        transaction.on_commit(lambda: storage.delete(file_name))
    return True
