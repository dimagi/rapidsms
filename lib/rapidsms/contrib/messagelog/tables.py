#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


from django.conf import settings
from djtables import Table, Column
from djtables.column import DateColumn
from .models import Message


class MessageTable(Table):

    # this is temporary, until i fix ModelTable!
    contact = Column()
    connection = Column()
    type = Column(value = lambda cell : cell.row.message_type, sortable = False)
    direction = Column()
    date = DateColumn(format="H:i d/m/Y")
    text = Column(css_class="message")

    class Meta:
        #model = Message
        #exclude = ['id']
        order_by = '-date'
