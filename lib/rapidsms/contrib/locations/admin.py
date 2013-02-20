#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

from django.contrib import admin
from models import Location, LocationType, Point

class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "type")
    list_filter = ('type', 'is_active')
    model = Location

class LocationTypeAdmin(admin.ModelAdmin):
    model = LocationType

admin.site.register(Point)
admin.site.register(Location, LocationAdmin)
admin.site.register(LocationType, LocationTypeAdmin)

