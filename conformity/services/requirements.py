def compute_hierarchy_fields(instance):
    """Retain the existing natural key until its migration is planned."""
    instance.name = f'{instance.parent.name}-{instance.code}' if instance.parent else instance.code
