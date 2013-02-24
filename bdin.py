#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# Copyright (C) 2013 Rodrigo Pinheiro Marques de Araujo
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.


LICENSE = """ Copyright (C) 2013 Rodrigo Pinheiro Marques de Araujo

 This program is free software; you can redistribute it and/or modify it under
 the terms of the GNU General Public License as published by the Free Software
 Foundation; either version 2 of the License, or (at your option) any later
 version.

 This program is distributed in the hope that it will be useful, but WITHOUT
 ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
 details.

 You should have received a copy of the GNU General Public License along with
 this program; if not, write to the Free Software Foundation, Inc., 51
 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA."""



import dbus
import pygtk
pygtk.require('2.0')
import gtk
import gobject
import appindicator
from dbus.mainloop.glib import DBusGMainLoop


class UmountError(BaseException):
    pass

class MountError(BaseException):
    pass

class DetachError(BaseException):
    pass


class Device(object):

    def __init__(self, udisk_obj):
        self.obj = udisk_obj
        self.props = dbus.Interface(self.obj, dbus.PROPERTIES_IFACE)


    def __repr__(self):
        return "Device(file={},label={})".format(self.device_file,
                self.name)

    @property
    def is_partition(self):
        return bool(self.props.Get("org.freedesktop.UDisks.Device", 
                                   'DeviceIsPartition'))

    @property
    def name(self):
        return self.props.Get("org.freedesktop.UDisks.Device", 
                              'idLabel')

    @property
    def is_internal(self):
        return bool(self.props.Get("org.freedesktop.UDisks.Device", 
                              'DeviceIsSystemInternal'))

    @property
    def is_mounted(self):
        return bool(self.props.Get("org.freedesktop.UDisks.Device", 
                              'DeviceIsMounted'))

    @property
    def device_file(self):
        return self.props.Get("org.freedesktop.UDisks.Device", 
                             'DeviceFile')

        
    def mount(self):
        try:
            return unicode(self.obj.FilesystemMount('',''))
        except dbus.DBusException, e:
            raise MountError(e.message)

    def unmount(self):
        try:
            return self.obj.FilesystemUnmount('')
        except dbus.DBusException, e:
            raise UmountError(e.message)


    def detach(self):

        slave = self.props.Get("org.freedesktop.UDisks.Device", 
                               'PartitionSlave')
        bus = dbus.SystemBus()
        drive_device_obj = bus.get_object("org.freedesktop.UDisks", slave)
        drive_device_dbus = dbus.Interface(drive_device_obj, "org.freedesktop.UDisks.Device")
        try:
            drive_device_dbus.DriveDetach('')
        except dbus.DBusException, e:
            raise DetachError(e)



class UdiskManager(object):
    
    def __init__(self, callback):
        self.bus = dbus.SystemBus()

        self.proxy = self.bus.get_object("org.freedesktop.UDisks", 
                                   "/org/freedesktop/UDisks")
        self.iface = dbus.Interface(self.proxy, "org.freedesktop.UDisks")


        def mycallback( *args ):
            callback()

        self.iface.connect_to_signal('DeviceAdded', mycallback)
        self.iface.connect_to_signal('DeviceRemoved', mycallback)
        self.iface.connect_to_signal('DeviceChanged', mycallback)


    def list_devices(self):
        result = []
        for dev in self.iface.EnumerateDevices():
            device_obj = self.bus.get_object("org.freedesktop.UDisks", dev)
            device_dbus = dbus.Interface(device_obj, "org.freedesktop.UDisks.Device") 
            device = Device(device_dbus)
            if (not device.is_internal) and device.is_partition:
                result.append(device)
            else:
                continue

        return result


def display_exception(method):
    try:
        method()
    except (MountError, UmountError, DetachError), e:
        dialog = gtk.MessageDialog(None, 0, gtk.MESSAGE_ERROR, 
                                    gtk.BUTTONS_CLOSE, e.message)
        dialog.set_title("Bdin")
        response = dialog.run()
        dialog.destroy()



class App(object):


    def __init__(self):
        self.ind = appindicator.Indicator("bdin",
                                          "indicator-messages", 
                                          appindicator.CATEGORY_APPLICATION_STATUS)
        self.ind.set_status(appindicator.STATUS_ACTIVE)
        self.ind.set_icon("block-device")
        self.manager = UdiskManager(self.menu_setup)
        self.menu_setup()


    def menu_setup(self):
        self.menu = gtk.Menu()

        for dev in self.manager.list_devices():
            name = "{} on {}".format(dev.name, dev.device_file)
            item = gtk.MenuItem(name)
            item.show()

            d_e = display_exception

            if not dev.is_mounted:
                submenu = gtk.Menu()
                mount_item = gtk.MenuItem("Mount")
                mount_item.show()
                mount_item.connect("activate", lambda i,d: d_e(d.mount), dev)
                submenu.append(mount_item)

                detach_item = gtk.MenuItem("Detach")
                detach_item.show()
                detach_item.connect("activate", lambda i,d: d_e(d.detach), dev)
                submenu.append(detach_item)
            else:
                submenu = gtk.Menu()
                unmount_item = gtk.MenuItem("Unmount")
                unmount_item.show()
                unmount_item.connect("activate", lambda i,d : d_e(d.unmount), dev)
                submenu.append(unmount_item)


            
            item.set_submenu(submenu)
            self.menu.append(item)


        about = gtk.ImageMenuItem("About")
        img = gtk.Image()
        img.set_from_stock(gtk.STOCK_ABOUT, gtk.ICON_SIZE_MENU)
        about.set_image(img)
        about.connect('activate', lambda i: self.show_about())
        about.show()
        self.menu.append(about)


        image = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        image.connect("activate", self.quit)
        image.show()
        self.menu.append(image)
                    
        self.menu.show()
        self.ind.set_menu(self.menu)


    def quit(self, widget, data=None):
        gtk.main_quit()


    def show_about(self):
        self.about = gtk.AboutDialog()
        self.about.set_name("Bdin")
        self.about.set_version("0.1")
        self.about.set_comments("A block device appindicator for ubuntu")
        self.about.set_copyright("Copyright (C) 2013 Rodrigo Pinheiro Marques de Araujo")
        self.about.set_authors(["Rodrigo Pinheiro Marques de Araujo <fenrrir@gmail.com>"])
        self.about.set_license(LICENSE)
        self.about.set_program_name("Bdin")
        self.about.set_website("github.com/fenrrir/bdin")
        self.about.run()
        self.about.destroy()



def main():
    DBusGMainLoop(set_as_default=True)
    app = App()
    gtk.main()


if __name__ == "__main__":
    main()
