// A drawn glass card: translucent fill, a fine light-facing border, an edge light along
// the top and a soft shadow. No blur (cheap with software rendering).
import QtQuick

Item {
    id: glass
    property real radius: 20
    property real tint: 0.70
    default property alias content: inner.data

    Rectangle {
        anchors.fill: parent
        anchors.topMargin: 8
        anchors.margins: -6
        radius: glass.radius + 6
        color: Qt.rgba(0, 0, 0, 0.22)
    }
    Rectangle {
        anchors.fill: parent
        radius: glass.radius
        color: Qt.rgba(0.07, 0.11, 0.18, glass.tint)
        border.color: Qt.rgba(1, 1, 1, 0.13)
        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 1 }
            height: 1
            color: Qt.rgba(0.62, 0.95, 1.0, 0.32)
        }
    }
    Item { id: inner; anchors.fill: parent }
}
