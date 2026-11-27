// One application in the grid: icon, name, summary and the publisher state. The card is
// a button (click, or Tab and Enter) that opens the details.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: card
    required property var app
    signal open()

    implicitWidth: 300
    implicitHeight: 96
    radius: 16
    color: hover.hovered || activeFocus ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(1, 1, 1, 0.07)
    border.color: activeFocus ? "#4fd1e8" : Qt.rgba(1, 1, 1, 0.12)
    border.width: activeFocus ? 2 : 1
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: app.name
    Accessible.description: app.summary
    Accessible.onPressAction: card.open()
    Keys.onReturnPressed: card.open()
    Keys.onSpacePressed: card.open()
    HoverHandler { id: hover }
    TapHandler { onTapped: card.open() }

    RowLayout {
        anchors { fill: parent; margins: 14 }
        spacing: 14
        Rectangle {
            Layout.preferredWidth: 64; Layout.preferredHeight: 64
            radius: 14
            color: Qt.rgba(1, 1, 1, 0.06)
            Image {
                anchors { fill: parent; margins: 4 }
                source: card.app.icon || ""
                sourceSize.width: 128
                fillMode: Image.PreserveAspectFit
                asynchronous: true
            }
            Label {
                anchors.centerIn: parent
                visible: !card.app.icon
                text: card.app.name.length > 0 ? card.app.name[0] : "?"
                color: "#eef6fb"
                font { family: "Inter"; pixelSize: 26 }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            Label {
                Layout.fillWidth: true
                text: card.app.name
                color: "#eef6fb"
                elide: Text.ElideRight
                font { family: "Inter"; pixelSize: 15; weight: Font.DemiBold }
            }
            Label {
                Layout.fillWidth: true
                text: card.app.summary
                color: "#a9b8c6"
                elide: Text.ElideRight
                font { family: "Inter"; pixelSize: 12 }
            }
            Label {
                text: card.app.installed ? "Installed"
                    : (card.app.verified ? "✓ Verified publisher" : "Publisher not verified")
                color: card.app.installed ? "#4fd1e8" : (card.app.verified ? "#5fd39a" : "#a9b8c6")
                font { family: "Inter"; pixelSize: 11 }
            }
        }
    }
}
