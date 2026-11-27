// An application's page: what it is, who publishes it, what it may access, screenshots,
// and Install / Open / Update / Remove with progress. Verification is explained as what
// it is (Flathub confirmed the publisher), never as a promise that the app is safe.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Flickable {
    id: page
    required property var app
    signal back()
    property var permissions: []
    readonly property bool installed: center.installedIds.indexOf(app.id) >= 0
    readonly property bool updatable: center.updateIds.indexOf(app.id) >= 0

    contentHeight: column.implicitHeight + 40
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar {}

    Connections {
        target: center
        function onPermissionsReady(id, list) {
            if (id === page.app.id) page.permissions = list;
        }
    }
    Component.onCompleted: center.loadPermissions(app.id)

    ColumnLayout {
        id: column
        width: page.width - 40
        x: 20
        y: 20
        spacing: 16

        Button {
            text: "‹ Back"
            Accessible.name: "Back to the list"
            onClicked: page.back()
        }

        RowLayout {
            spacing: 18
            Rectangle {
                Layout.preferredWidth: 96; Layout.preferredHeight: 96
                radius: 20
                color: Qt.rgba(1, 1, 1, 0.06)
                Image {
                    anchors { fill: parent; margins: 6 }
                    source: page.app.icon || ""
                    sourceSize.width: 128
                    fillMode: Image.PreserveAspectFit
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Label {
                    text: page.app.name
                    color: "#eef6fb"
                    font { family: "Inter"; pixelSize: 28; weight: Font.DemiBold }
                    Accessible.role: Accessible.Heading
                }
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: page.app.summary
                    color: "#a9b8c6"
                    font { family: "Inter"; pixelSize: 15 }
                }
                Label {
                    text: (page.app.developer ? "By " + page.app.developer + "  ·  " : "")
                        + (page.app.license ? "Licence " + page.app.license : "")
                    color: "#a9b8c6"
                    font { family: "Inter"; pixelSize: 12 }
                }
            }
            ColumnLayout {
                spacing: 8
                Button {
                    visible: !page.installed
                    text: "Install"
                    highlighted: true
                    enabled: !center.busy
                    Accessible.name: "Install " + page.app.name
                    onClicked: center.install(page.app.id)
                }
                Button {
                    visible: page.installed
                    text: "Open"
                    highlighted: true
                    Accessible.name: "Open " + page.app.name
                    onClicked: center.launch(page.app.id)
                }
                Button {
                    visible: page.installed && page.updatable
                    text: "Update"
                    enabled: !center.busy
                    Accessible.name: "Update " + page.app.name
                    onClicked: center.update(page.app.id)
                }
                Button {
                    visible: page.installed
                    text: "Remove"
                    enabled: !center.busy
                    Accessible.name: "Remove " + page.app.name
                    onClicked: center.remove(page.app.id)
                }
            }
        }

        // --- publisher -----------------------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: publisher.implicitHeight + 28
            radius: 14
            color: Qt.rgba(1, 1, 1, 0.06)
            border.color: page.app.verified ? Qt.rgba(0.37, 0.83, 0.6, 0.5) : Qt.rgba(0.95, 0.77, 0.43, 0.5)
            ColumnLayout {
                id: publisher
                anchors { fill: parent; margins: 14 }
                spacing: 4
                Label {
                    text: page.app.verified ? "✓ Verified publisher" : "Publisher not verified"
                    color: page.app.verified ? "#5fd39a" : "#f2c46d"
                    font { family: "Inter"; pixelSize: 15; weight: Font.DemiBold }
                }
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: "#a9b8c6"
                    font { family: "Inter"; pixelSize: 13 }
                    text: page.app.verified
                        ? "Flathub has confirmed that this app is published by its developer. This "
                          + "does not mean AEGIS or Flathub has checked that the app is safe: its "
                          + "permissions below show what it can access."
                        : "Flathub has not confirmed who publishes this app. Its permissions below "
                          + "show what it can access."
                }
            }
        }

        // --- permissions ---------------------------------------------------------------
        Label {
            text: "What it can access"
            color: "#eef6fb"
            font { family: "Inter"; pixelSize: 17; weight: Font.DemiBold }
        }
        Label {
            visible: page.permissions.length === 0
            text: "Reading the permissions…"
            color: "#a9b8c6"
            font.family: "Inter"
        }
        Repeater {
            model: page.permissions
            delegate: RowLayout {
                required property var modelData
                spacing: 10
                Rectangle {
                    width: 10; height: 10; radius: 5
                    color: modelData.level === "high" ? "#ff6b6b"
                         : modelData.level === "medium" ? "#f2c46d"
                         : modelData.level === "low" ? "#5fd39a" : "#8d9aa8"
                }
                Label {
                    text: modelData.text
                    color: "#eef6fb"
                    font { family: "Inter"; pixelSize: 14 }
                    Accessible.name: modelData.text + " (" + modelData.level + ")"
                }
            }
        }
        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: "#a9b8c6"
            font { family: "Inter"; pixelSize: 12 }
            text: "Red: broad access to your files, devices or other programs. Yellow: worth "
                + "knowing. Green: routine. Installed for your account only; no administrator "
                + "password is needed."
        }

        // --- screenshots and description -------------------------------------------------
        Row {
            Layout.fillWidth: true
            spacing: 12
            visible: page.app.screenshots && page.app.screenshots.length > 0
            Repeater {
                model: page.app.screenshots || []
                delegate: Image {
                    required property string modelData
                    width: Math.min(360, (column.width - 24) / 3)
                    height: width * 0.6
                    source: modelData
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                }
            }
        }
        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: page.app.description
            color: "#dbe4ec"
            font { family: "Inter"; pixelSize: 14 }
        }
    }
}
