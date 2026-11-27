// Scene 2, Meet your desktop: open the real launcher and the real file manager from the
// dock (completed by window events reported from KWin), and a drag-and-drop practice
// with a dock replica (practice inside this window; keyboard: focus an icon, Enter).
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import AegisWelcome

Item {
    id: scene

    Connections {
        target: welcome
        function onWindowEvent(event) {
            if (event.event !== "added")
                return;
            if (event.plasma && event.w > 200 && event.h > 200)
                welcome.complete("desktop.launcher");
            if (event.cls === "org.kde.dolphin")
                welcome.complete("desktop.files");
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 24

        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            spacing: 12
            Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: "#a9b8c6"
                font { family: "Inter"; pixelSize: 15 }
                text: "At the bottom floats the dock: the launcher with the AEGIS mark, your "
                    + "pinned and running applications, and the security status. At the top: "
                    + "the application in front, search, Quick Settings and the clock."
            }
            Step {
                key: "desktop.launcher"
                title: "Open the launcher"
                hint: "Click the AEGIS mark at the left end of the dock, or press the Meta "
                    + "(Windows) key. Close it again with Escape."
            }
            Step {
                key: "desktop.files"
                title: "Open Files from the dock"
                hint: "Click the blue folder in the dock, or press Meta+E."
            }
            Step {
                key: "desktop.drag"
                title: "Practice: drag an application onto the dock"
                hint: "Drag one of the icons on the right onto the glass dock below them. "
                    + "Keyboard: Tab to an icon and press Enter."
            }
            Item { Layout.fillHeight: true }
        }

        Glass {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.fillHeight: true
            radius: 22

            Label {
                anchors { top: parent.top; horizontalCenter: parent.horizontalCenter; topMargin: 18 }
                text: "Practice dock"
                color: "#a9b8c6"
                font { family: "Inter"; pixelSize: 13 }
            }
            Row {
                id: palette
                anchors { top: parent.top; horizontalCenter: parent.horizontalCenter; topMargin: 60 }
                spacing: 22
                Repeater {
                    model: [{ name: "Files", icon: "📁" }, { name: "Terminal", icon: "⌨" },
                            { name: "Settings", icon: "⚙" }]
                    delegate: Rectangle {
                        id: icon
                        required property var modelData
                        width: 64; height: 64; radius: 16
                        color: activeFocus ? "#1d3b5c" : "#12304f"
                        border.color: activeFocus ? "#4fd1e8" : Qt.rgba(1, 1, 1, 0.2)
                        activeFocusOnTab: true
                        Accessible.role: Accessible.Button
                        Accessible.name: "Place " + modelData.name + " on the practice dock"
                        Accessible.onPressAction: dock.place(modelData.name)
                        Drag.active: dragArea.drag.active
                        Drag.hotSpot.x: 32; Drag.hotSpot.y: 32
                        Label {
                            anchors.centerIn: parent
                            text: icon.modelData.icon
                            font.pixelSize: 28
                            color: "#eef6fb"
                        }
                        MouseArea {
                            id: dragArea
                            anchors.fill: parent
                            drag.target: icon
                            onReleased: {
                                if (icon.Drag.target)
                                    dock.place(icon.modelData.name);
                                icon.x = 0; icon.y = 0;
                                palette.forceLayout();
                            }
                        }
                        Keys.onReturnPressed: dock.place(modelData.name)
                        Keys.onSpacePressed: dock.place(modelData.name)
                    }
                }
            }
            Rectangle {
                id: dock
                property var placed: []
                function place(name) {
                    if (placed.indexOf(name) < 0)
                        placed = placed.concat([name]);
                    welcome.complete("desktop.drag");
                }
                anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter; bottomMargin: 26 }
                width: Math.max(220, placed.length * 74 + 40)
                height: 84
                radius: 24
                color: dropArea.containsDrag ? Qt.rgba(0.31, 0.82, 0.91, 0.25) : Qt.rgba(1, 1, 1, 0.08)
                border.color: Qt.rgba(0.62, 0.95, 1.0, 0.45)
                Behavior on width { NumberAnimation { duration: (welcome.reducedMotion ? 0 : 250); easing.type: Easing.OutCubic } }
                Accessible.role: Accessible.Grouping
                Accessible.name: "Practice dock"
                DropArea { id: dropArea; anchors.fill: parent }
                Row {
                    anchors.centerIn: parent
                    spacing: 10
                    Repeater {
                        model: dock.placed
                        delegate: Rectangle {
                            required property string modelData
                            width: 64; height: 64; radius: 16
                            color: "#1d3b5c"
                            Label { anchors.centerIn: parent; text: modelData; color: "#eef6fb"; font.pixelSize: 11 }
                        }
                    }
                }
                Label {
                    anchors.centerIn: parent
                    visible: dock.placed.length === 0
                    text: "Drop here"
                    color: "#a9b8c6"
                }
            }
        }
    }
}
