// Do Not Disturb through Plasma's own notification settings (the module the Plasma
// notifications applet uses). Loaded separately by main.qml, so that a change in that
// module disables only this tile, not the panel.
import QtQuick
import org.kde.notificationmanager as NotificationManager

Tile {
    id: dnd
    readonly property bool active: settings.notificationsInhibitedUntil > new Date()

    iconName: active ? "notifications-disabled" : "notifications"
    title: "Do Not Disturb"
    detail: active ? "On" : "Off"
    toggle: true
    checked: active

    NotificationManager.Settings {
        id: settings
    }

    onActivated: {
        const until = new Date();
        // "On" lasts until it is switched off (a year is the longest Plasma offers).
        until.setFullYear(until.getFullYear() + (dnd.active ? -1 : 1));
        settings.notificationsInhibitedUntil = until;
        settings.save();
    }
}
