// AEGIS top bar, left end (v3, M10): the AEGIS mark, which opens the launcher, and the
// name of the application in front ("Desktop" when none), in the AEGIS type. Read-only
// use of Plasma's task model; the launcher is opened through plasmashell's own D-Bus
// method, as the Meta key does.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.plasma5support as P5Support
import org.kde.taskmanager as TaskManager
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    preferredRepresentation: fullRepresentation
    Plasmoid.backgroundHints: "NoBackground"

    TaskManager.TasksModel {
        id: tasks
        groupMode: TaskManager.TasksModel.GroupDisabled
    }
    readonly property string appName: tasks.activeTask.valid
        ? (tasks.data(tasks.activeTask, TaskManager.AbstractTasksModel.AppName) || "")
        : ""

    P5Support.DataSource {
        id: executable
        engine: "executable"
        connectedSources: []
        onNewData: (source) => disconnectSource(source)
    }

    fullRepresentation: RowLayout {
        spacing: Kirigami.Units.smallSpacing * 2
        Layout.minimumWidth: implicitWidth

        PlasmaComponents.ToolButton {
            id: mark
            icon.name: "aegis-os"
            display: PlasmaComponents.AbstractButton.IconOnly
            text: "AEGIS launcher"
            Accessible.name: "Open the AEGIS launcher"
            Layout.preferredHeight: root.height
            Layout.preferredWidth: root.height
            onClicked: executable.connectSource(
                "busctl --user call org.kde.plasmashell /PlasmaShell "
                + "org.kde.PlasmaShell activateLauncherMenu")
        }
        PlasmaComponents.Label {
            text: root.appName.length > 0 ? root.appName : "Desktop"
            font.weight: Font.DemiBold
            elide: Text.ElideRight
            Layout.maximumWidth: Kirigami.Units.gridUnit * 14
            Accessible.name: "Active application: " + text
        }
    }
}
