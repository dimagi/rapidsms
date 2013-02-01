from django.db import transaction

@transaction.commit_on_success
def pre_save_connection(sender, instance, **kwargs):
    """ 
    when a connection is modified, ensure that if contact is changed
    the old contact's default_connection is updated appropriately
    """
    from rapidsms.models import Connection
    try:
        old_contact = Connection.objects.get(pk=instance.pk).contact
    except Connection.DoesNotExist:
        return
    if old_contact and ((instance.contact is None) or 
                        (instance.contact != old_contact)):
        if old_contact.connection_set.count() > 1:
            connections = old_contact.connection_set.all().order_by('-pk')
            for conn in connections:
                if conn != instance.contact:
                    old_contact.default_connection = conn
                    break 
        else:
            old_contact.default_connection = None
        old_contact.save()

@transaction.commit_on_success
def post_save_connection(sender, instance, created, **kwargs):
    """
    when a new connection is created, auto-set it to the contact's 
    default_connection
    """
    if instance.contact and instance.contact.default_connection is None:
        instance.contact.default_connection = instance
        instance.contact.save()
    
@transaction.commit_on_success
def post_delete_connection(sender, instance, **kwargs):
    """
    when a connection is created, update the contact's default_connection
    """
    contact = instance.contact
    if contact:
        contact.update_default_connection()

