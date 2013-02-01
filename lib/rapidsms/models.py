#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


from datetime import datetime
from django.db import models
from django.db.models.signals import post_save, post_delete, pre_save
from .utils.modules import try_import, get_classes
from .errors import NoConnectionError, MessageSendingError
from .conf import settings
from .signals import post_save_connection, post_delete_connection, \
    pre_save_connection


class ExtensibleModelBase(models.base.ModelBase):
    def __new__(cls, name, bases, attrs):
        module_name = attrs["__module__"]
        app_label = module_name.split('.')[-2]
        extensions = _find_extensions(app_label, name)
        bases = tuple(extensions) + bases

        return super(ExtensibleModelBase, cls).__new__(
            cls, name, bases, attrs)


def _find_extensions(app_label, model_name):
    ext = []

    suffix = "extensions.%s.%s" % (
        app_label, model_name.lower())

    modules = filter(None, [
        try_import("%s.%s" % (app_name, suffix))
        for app_name in settings.INSTALLED_APPS ])

    for module in modules:
        for cls in get_classes(module, models.Model):
            ext.append(cls)

    return ext


class Backend(models.Model):
    """
    This model isn't really a backend. Those are regular Python classes,
    in rapidsms/backends. This is just a stub model to provide a primary
    key for each running backend, so other models can be linked to it
    with ForeignKeys.
    """

    name = models.CharField(max_length=20, unique=True)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return '<%s: %s>' %\
            (type(self).__name__, self)


class App(models.Model):
    """
    This model isn't really a RapidSMS App. Like Backend, it's just a
    stub model to provide a primary key for each app, so other models
    can be linked to it.

    The Django ContentType stuff doesn't quite work here, since not all
    RapidSMS apps are valid Django apps. It would be nice to fill in the
    gaps and inherit from it at some point in the future.

    Instances of this model are generated by the update_apps management
    command, (which is hooked on Router startup (TODO: webui startup)),
    and probably shouldn't be messed with after that.
    """

    module = models.CharField(max_length=100, unique=True)
    active = models.BooleanField()

    def __unicode__(self):
        return self.module

    def __repr__(self):
        return '<%s: %s>' %\
            (type(self).__name__, self)


class ContactBase(models.Model):
    name  = models.CharField(max_length=100, blank=True)

    # the spec: http://www.w3.org/International/articles/language-tags/Overview
    # reference:http://www.iana.org/assignments/language-subtag-registry
    language = models.CharField(max_length=6, blank=True, help_text=
        "The language which this contact prefers to communicate in, as "
        "a W3C language tag. If this field is left blank, RapidSMS will "
        "default to: " + settings.LANGUAGE_CODE)
    default_connection  = models.ForeignKey('Connection', null=True, 
                                            blank=True, 
                                            related_name='contact+', 
                                            on_delete=models.SET_NULL)

    class Meta:
        abstract = True

    def __unicode__(self):
        return self.name or "Anonymous"

    def __repr__(self):
        return '<%s: %s>' %\
            (type(self).__name__, self)

    @property
    def is_anonymous(self):
        return not self.name

    def message(self, template, **kwargs):
        """
        Attempt to send a message to this contact via their default
        connection. Like any outgoing message, it may be aborted during
        the ``outgoing`` phase, or be rejected by the backend. In these
        cases, MessageSendingError is raised. If no default connection
        exists, NoConnectionError is raised.
        """

        if self.default_connection is None:
            raise NoConnectionError()

        was_sent = self.default_connection.message(
            template, **kwargs)

        if not was_sent:
            raise MessageSendingError()

        return True

    def set_default_connection_identity(self, phone_number, backend_name):
        """ 
        set the phone number of the default connection
        CAUTION: if a connection with the same identity/backend already exists,
        this function will steal it.
        """
        if not phone_number:
            return None
        conn = self.default_connection
        if not conn:
            backend = Backend.objects.get(name=backend_name)
            try:
                conn = Connection.objects.get(backend=backend, 
                                              identity=phone_number)
            except Connection.DoesNotExist:
                # good, it doesn't exist already
                conn = Connection(backend=backend,
                                  contact=self)
            else: 
                # this connection already exists - so we steal it
                conn.contact = self
        conn.identity = phone_number
        conn.save()
        return conn

    def update_default_connection(self):
        if self.default_connection is None:
            # default to the connection with the smallest pk
            if self.connection_set.count() > 0:
                self.default_connection = self.connection_set.all().order_by('-pk')[0]            
                self.save()

class Contact(ContactBase):
    __metaclass__ = ExtensibleModelBase


class ConnectionBase(models.Model):
    backend  = models.ForeignKey(Backend)
    identity = models.CharField(max_length=100)
    contact  = models.ForeignKey(Contact, null=True, blank=True)

    class Meta:
        abstract = True
        unique_together = (('backend', 'identity'),)

    def __unicode__(self):
        return "%s via %s" %\
            (self.identity, self.backend)

    def __repr__(self):
        return '<%s: %s>' %\
            (type(self).__name__, self)

    def message(self, template, **kwargs):
        """
        Attempt to send a message to this connection. Like any outgoing
        message, it may be aborted during the ``outgoing`` phase, or be
        rejected by the backend. In these cases, MessageSendingError is
        raised. (There is currently no way to know *why* the message was
        not sent, so we raise a generic error.)

        This method can only be called in the ``runrouter`` process,
        since the router is currently not accessible from the webui
        process(es). If no router is running, NoRouterError is raised
        (by the ``OutgoingMessage.send`` method).
        """

        from .messages.outgoing import OutgoingMessage
        was_sent = OutgoingMessage(self, template, **kwargs).send()

        if not was_sent:
            raise MessageSendingError()

        return True


class Connection(ConnectionBase):
    """
    This model pairs a Backend object with an identity unique to it (eg.
    a phone number, email address, or IRC nick), so RapidSMS developers
    need not worry about which backend a messge originated from.
    """

    __metaclass__ = ExtensibleModelBase

pre_save.connect(pre_save_connection, sender=Connection)
post_save.connect(post_save_connection, sender=Connection)
post_delete.connect(post_delete_connection, sender=Connection)

class DeliveryReport(models.Model):
    '''
    This model is used for delivery reports from sending SMS messages
    using a gateway.
    '''
    action = models.CharField(max_length=255)
    report_id = models.CharField(max_length=255, help_text='Gateway assigned ID')
    number = models.CharField(max_length=255, help_text='Destination telephone number')
    report = models.CharField(max_length=255, help_text='Actual report text')
