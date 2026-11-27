// Scene 3, Control your workspace: practise on a real Files window. KWin reports its
// geometry and state; each exercise completes when the real window does it:
//   moved      position changed by more than 40 px at the same size
//   resized    size changed by more than 40 px (not by snapping or maximising)
//   snapped    exactly half of the work area, at its left or right edge
//   maximised  the whole work area
//   minimised  KWin's minimised state
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import AegisWelcome

Item {
    id: scene
    property var settled: null   // the window as it was when it last stood still
    property var latest: null    // the last report, for the live view

    function near(a, b) { return Math.abs(a - b) <= 4; }

    Timer {
        id: settle
        interval: 700
        onTriggered: scene.settled = scene.latest
    }

    Connections {
        target: welcome
        function onWindowEvent(e) {
            if (e.cls !== "org.kde.dolphin" || !e.normal)
                return;
            const maximised = near(e.x, e.ax) && near(e.y, e.ay) && near(e.w, e.aw) && near(e.h, e.ah);
            const snapped = !maximised && near(e.w, e.aw / 2) && near(e.h, e.ah)
                && (near(e.x, e.ax) || near(e.x + e.w, e.ax + e.aw));
            const state = Object.assign({ maximised: maximised, snapped: snapped }, e);
            if (e.minimized)
                welcome.complete("workspace.minimise");
            if (maximised)
                welcome.complete("workspace.maximise");
            if (snapped)
                welcome.complete("workspace.snap");
            const b = scene.settled;
            const plain = s => !s.minimized && !s.maximised && !s.snapped;
            if (b && plain(b) && plain(state)) {
                if (near(e.w, b.w) && near(e.h, b.h) && (Math.abs(e.x - b.x) > 40 || Math.abs(e.y - b.y) > 40))
                    welcome.complete("workspace.move");
                if (Math.abs(e.w - b.w) > 40 || Math.abs(e.h - b.h) > 40)
                    welcome.complete("workspace.resize");
            }
            scene.latest = state;
            if (!scene.settled)
                scene.settled = state;
            settle.restart();
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 24

        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 3
            spacing: 10
            Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: "#a9b8c6"
                font { family: "Inter"; pixelSize: 15 }
                text: "Practise on a real window. This tour stays on top, at the side, so you "
                    + "can follow along."
            }
            Button {
                text: "Open a practice window"
                Accessible.name: "Open a Files window to practise with"
                onClicked: welcome.openFiles()
            }
            Step {
                key: "workspace.move"
                title: "Move the window"
                hint: "Drag its title bar, or hold Meta and drag anywhere in the window."
            }
            Step {
                key: "workspace.resize"
                title: "Resize it"
                hint: "Hold Meta and drag with the right mouse button inside the window."
            }
            Step {
                key: "workspace.snap"
                title: "Snap it to half of the screen"
                hint: "Drag it against the left or right screen edge, or press Meta+← / Meta+→."
            }
            Step {
                key: "workspace.maximise"
                title: "Maximise it"
                hint: "Double-click the title bar, drag it to the top edge, or press Meta+PgUp."
            }
            Step {
                key: "workspace.minimise"
                title: "Minimise it, then bring it back"
                hint: "The _ button in the title bar or Meta+PgDown; bring it back from the dock."
            }
            Item { Layout.fillHeight: true }
        }

        // A small live diagram of what KWin reported last (only when there is room: in this
        // scene the tour is a narrow side panel).
        Glass {
            visible: scene.width > 700
            Layout.fillWidth: true
            Layout.preferredWidth: 2
            Layout.fillHeight: true
            radius: 22
            Label {
                anchors { top: parent.top; horizontalCenter: parent.horizontalCenter; topMargin: 14 }
                text: welcome.watching ? "Your screen, live" : "Live view unavailable (skip steps instead)"
                color: "#a9b8c6"
                font { family: "Inter"; pixelSize: 13 }
            }
            Item {
                id: screen
                anchors { fill: parent; margins: 36; topMargin: 46 }
                readonly property var e: scene.latest
                readonly property real k: e ? Math.min(width / (e.ax + e.aw), height / (e.ay + e.ah)) : 1
                Rectangle {
                    anchors.fill: parent
                    color: Qt.rgba(1, 1, 1, 0.04)
                    border.color: Qt.rgba(1, 1, 1, 0.15)
                    radius: 6
                }
                Rectangle {
                    visible: screen.e !== null && !screen.e.minimized
                    x: screen.e ? screen.e.x * screen.k : 0
                    y: screen.e ? screen.e.y * screen.k : 0
                    width: screen.e ? screen.e.w * screen.k : 0
                    height: screen.e ? screen.e.h * screen.k : 0
                    radius: 4
                    color: Qt.rgba(0.31, 0.82, 0.91, 0.25)
                    border.color: "#4fd1e8"
                    Behavior on x { NumberAnimation { duration: (welcome.reducedMotion ? 0 : 150) } }
                    Behavior on y { NumberAnimation { duration: (welcome.reducedMotion ? 0 : 150) } }
                    Behavior on width { NumberAnimation { duration: (welcome.reducedMotion ? 0 : 150) } }
                    Behavior on height { NumberAnimation { duration: (welcome.reducedMotion ? 0 : 150) } }
                }
            }
        }
    }
}
