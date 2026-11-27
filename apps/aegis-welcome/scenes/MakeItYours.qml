// Scene 4, Make it yours: AEGIS Dark or Light, the Liquid Glass profile and the
// wallpaper, each applied to the real desktop at once (as the user, through the Quick
// Settings helper and plasma-apply-wallpaperimage). "Undo" restores what was there when
// the scene opened.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import AegisWelcome

Item {
    id: scene
    property var start: ({})
    property var facts: ({})
    readonly property var papers: welcome.wallpapers()
    property string paper: ""

    function read() {
        const out = welcome.quickSettings(["status"]);
        const parsed = {};
        for (const line of out.split("\n")) {
            const at = line.indexOf("=");
            if (at > 0) parsed[line.slice(0, at)] = line.slice(at + 1);
        }
        facts = parsed;
        return parsed;
    }
    function scheme(name) {
        welcome.quickSettings(["scheme", name]);
        read();
        welcome.complete("yours.scheme");
    }
    function glass(profile) {
        welcome.quickSettings(["glass", profile]);
        read();
        welcome.complete("yours.glass");
    }
    function wallpaper(path) {
        welcome.applyWallpaper(path);
        paper = path;
        welcome.complete("yours.wallpaper");
    }
    Component.onCompleted: start = read()

    ColumnLayout {
        anchors.fill: parent
        spacing: 14
        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: "#a9b8c6"
            font { family: "Inter"; pixelSize: 15 }
            text: "Every choice here changes your desktop right away. Undo puts everything back."
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: 2
            columnSpacing: 18
            rowSpacing: 14

            Glass {
                Layout.fillWidth: true
                Layout.preferredHeight: 150
                ColumnLayout {
                    anchors { fill: parent; margins: 18 }
                    Label { text: "Light or dark"; color: "#eef6fb"; font { family: "Inter"; pixelSize: 16; weight: Font.DemiBold } }
                    RowLayout {
                        spacing: 12
                        Repeater {
                            model: [{ id: "dark", label: "AEGIS Dark", bg: "#0e1628", fg: "#eef6fb" },
                                    { id: "light", label: "AEGIS Light", bg: "#e9eef4", fg: "#0e1628" }]
                            delegate: Rectangle {
                                required property var modelData
                                readonly property bool chosen: (scene.facts.scheme === "AEGISLight") === (modelData.id === "light")
                                width: 150; height: 76; radius: 14
                                color: modelData.bg
                                border.color: chosen ? "#4fd1e8" : Qt.rgba(1, 1, 1, 0.2)
                                border.width: chosen || activeFocus ? 3 : 1
                                activeFocusOnTab: true
                                // Button role: its accessibility action is "press" (run 46052351712).
                                Accessible.role: Accessible.Button
                                Accessible.name: modelData.label
                                Accessible.checkable: true
                                Accessible.checked: chosen
                                Accessible.onPressAction: scene.scheme(modelData.id)
                                Label { anchors.centerIn: parent; text: modelData.label; color: modelData.fg; font.family: "Inter" }
                                MouseArea { anchors.fill: parent; onClicked: scene.scheme(modelData.id) }
                                Keys.onReturnPressed: scene.scheme(modelData.id)
                                Keys.onSpacePressed: scene.scheme(modelData.id)
                            }
                        }
                    }
                }
            }

            Glass {
                Layout.fillWidth: true
                Layout.preferredHeight: 150
                ColumnLayout {
                    anchors { fill: parent; margins: 18 }
                    Label { text: "Liquid Glass"; color: "#eef6fb"; font { family: "Inter"; pixelSize: 16; weight: Font.DemiBold } }
                    Flow {
                        Layout.fillWidth: true
                        spacing: 8
                        Repeater {
                            model: [["auto", "Automatic"], ["full", "Full"], ["balanced", "Balanced"],
                                    ["performance", "Performance"]]
                            delegate: Button {
                                required property var modelData
                                text: modelData[1]
                                checkable: true
                                checked: (scene.facts.glass || "auto") === modelData[0]
                                Accessible.name: "Liquid Glass " + modelData[1]
                                onClicked: scene.glass(modelData[0])
                            }
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: "#a9b8c6"
                        font { family: "Inter"; pixelSize: 12 }
                        text: "Performance suits VirtualBox without 3D acceleration."
                    }
                }
            }

            Glass {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                Layout.fillHeight: true
                ColumnLayout {
                    anchors { fill: parent; margins: 18 }
                    Label { text: "Wallpaper"; color: "#eef6fb"; font { family: "Inter"; pixelSize: 16; weight: Font.DemiBold } }
                    RowLayout {
                        Layout.fillHeight: true
                        spacing: 14
                        Repeater {
                            model: scene.papers
                            delegate: Rectangle {
                                required property string modelData
                                Layout.preferredWidth: 180
                                Layout.preferredHeight: 104
                                radius: 12
                                clip: true
                                color: "#0e1628"
                                border.color: scene.paper === modelData ? "#4fd1e8" : Qt.rgba(1, 1, 1, 0.2)
                                border.width: scene.paper === modelData || activeFocus ? 3 : 1
                                activeFocusOnTab: true
                                Accessible.role: Accessible.Button
                                Accessible.name: "Wallpaper " + modelData.split("/")[4]
                                Accessible.onPressAction: scene.wallpaper(modelData)
                                Image {
                                    anchors { fill: parent; margins: 3 }
                                    source: "file://" + modelData
                                    sourceSize.width: 360
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                }
                                MouseArea { anchors.fill: parent; onClicked: scene.wallpaper(modelData) }
                                Keys.onReturnPressed: scene.wallpaper(modelData)
                            }
                        }
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Button {
                text: "Undo"
                Accessible.name: "Undo the changes made in this step"
                onClicked: {
                    scene.scheme(scene.start.scheme === "AEGISLight" ? "light" : "dark");
                    scene.glass(scene.start.glass || "auto");
                    if (scene.papers.length > 0)
                        scene.wallpaper(scene.papers[0]);
                }
            }
        }
    }
}
