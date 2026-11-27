// Scene 5, Explore applications: find an application by searching and read what it may
// access, in a small sample catalogue that works offline, then open the AEGIS App Center.
// "Verified publisher" means the store confirmed who publishes the app; it does not mean
// the app is safe: its permissions show what it can reach.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import AegisWelcome

Item {
    id: scene
    property var chosen: null
    readonly property var catalogue: [
        { name: "Google Chrome", summary: "Web browser from Google", category: "Internet", verified: true,
          permissions: ["Network", "Your Downloads folder", "Sound", "Camera and microphone (when you allow it)"] },
        { name: "Firefox", summary: "Web browser from Mozilla", category: "Internet", verified: true,
          permissions: ["Network", "Your Downloads folder", "Sound"] },
        { name: "LibreOffice", summary: "Documents, spreadsheets and presentations", category: "Office", verified: true,
          permissions: ["Your files (all of your home folder)", "Printing"] },
        { name: "GIMP", summary: "Image editor", category: "Graphics", verified: true,
          permissions: ["Your files (all of your home folder)"] },
        { name: "VLC", summary: "Plays almost any video or audio", category: "Audio and video", verified: false,
          permissions: ["Your files (all of your home folder)", "Sound", "Network"] },
        { name: "Thunderbird", summary: "E-mail and calendar", category: "Internet", verified: true,
          permissions: ["Network", "Your Downloads folder"] },
        { name: "Inkscape", summary: "Vector drawing", category: "Graphics", verified: true,
          permissions: ["Your files (all of your home folder)"] },
        { name: "Krita", summary: "Digital painting", category: "Graphics", verified: true,
          permissions: ["Your files (all of your home folder)", "Drawing tablets"] }
    ]
    readonly property var results: {
        const q = search.text.trim().toLowerCase();
        if (q.length === 0)
            return catalogue;
        return catalogue.filter(a => (a.name + " " + a.summary + " " + a.category).toLowerCase().indexOf(q) >= 0);
    }

    RowLayout {
        anchors.fill: parent
        spacing: 20
        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            spacing: 10
            Step {
                key: "apps.search"
                title: "Search for a web browser"
                hint: "Type \"browser\" in the search field."
            }
            Step {
                key: "apps.details"
                title: "Open an application and read its permissions"
                hint: "Choose one of the results."
            }
            TextField {
                id: search
                Layout.fillWidth: true
                placeholderText: "Search applications"
                Accessible.name: "Search applications"
                font.family: "Inter"
                onTextChanged: if (text.trim().length >= 2 && scene.results.length > 0) welcome.complete("apps.search")
            }
            // Type to search as soon as the scene is shown.
            Connections {
                target: welcome
                function onSceneChanged() {
                    if (welcome.scene === 4) search.forceActiveFocus();
                }
            }
            Component.onCompleted: if (welcome.scene === 4) search.forceActiveFocus()
            // A column of buttons (at most eight sample apps): each is a focusable,
            // accessible control (a ListView's delegates were not reachable through the
            // accessibility interface in run 46065804382).
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 6
                Repeater {
                    model: scene.results
                    delegate: Rectangle {
                        id: row
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: 40
                        radius: 10
                        color: hover.hovered || activeFocus ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(1, 1, 1, 0.06)
                        border.color: activeFocus ? "#4fd1e8" : "transparent"
                        activeFocusOnTab: true
                        Accessible.role: Accessible.Button
                        Accessible.name: modelData.name
                        Accessible.description: modelData.summary
                        Accessible.onPressAction: row.choose()
                        Keys.onReturnPressed: row.choose()
                        Keys.onSpacePressed: row.choose()
                        function choose() {
                            scene.chosen = row.modelData;
                            welcome.complete("apps.details");
                        }
                        HoverHandler { id: hover }
                        TapHandler { onTapped: row.choose() }
                        Label {
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter
                                      leftMargin: 12; rightMargin: 12 }
                            text: row.modelData.name + "  ·  " + row.modelData.summary
                            elide: Text.ElideRight
                            color: "#eef6fb"
                            font.family: "Inter"
                        }
                    }
                }
                Item { Layout.fillHeight: true }
            }
        }
        Glass {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.fillHeight: true
            ColumnLayout {
                anchors { fill: parent; margins: 20 }
                spacing: 10
                visible: scene.chosen !== null
                Label {
                    text: scene.chosen ? scene.chosen.name : ""
                    color: "#eef6fb"
                    font { family: "Inter"; pixelSize: 22; weight: Font.DemiBold }
                }
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: scene.chosen && scene.chosen.verified ? "✓ Verified publisher" : "Publisher not verified"
                    color: scene.chosen && scene.chosen.verified ? "#5fd39a" : "#f2c46d"
                    font { family: "Inter"; pixelSize: 14; weight: Font.DemiBold }
                }
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: "#a9b8c6"
                    font { family: "Inter"; pixelSize: 13 }
                    text: "Verified means the store has confirmed who publishes the app. It does not "
                        + "mean that AEGIS or the store has checked the app is safe: its permissions "
                        + "below show what it can access."
                }
                Label { text: "It can access:"; color: "#eef6fb"; font { family: "Inter"; pixelSize: 14 } }
                Repeater {
                    model: scene.chosen ? scene.chosen.permissions : []
                    delegate: Label {
                        required property string modelData
                        text: "•  " + modelData
                        color: "#eef6fb"
                        font.family: "Inter"
                    }
                }
                Item { Layout.fillHeight: true }
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: "#a9b8c6"
                    font { family: "Inter"; pixelSize: 12 }
                    text: "This is a practice catalogue. The AEGIS App Center shows the real one, "
                        + "installs for your account only and keeps the apps when you shut down."
                }
                Button {
                    text: "Open the AEGIS App Center"
                    onClicked: welcome.openAppCenter()
                }
            }
            Label {
                anchors.centerIn: parent
                visible: scene.chosen === null
                text: "Choose an application"
                color: "#a9b8c6"
                font.family: "Inter"
            }
        }
    }
}
