// AEGIS OS design tokens (GUI v1). The single source of colours, materials, spacing,
// radii, typography, shadows and motion for AEGIS QML components.
//
// Materials follow a layered glass model: translucent tint, backdrop blur supplied by
// the compositor (KWin's blur effect, configured in /etc/xdg/kwinrc;
// a QML item cannot sample what is behind its window), a fine light-facing border,
// a faint inner highlight and a soft shadow. Three variants only: regular, elevated,
// control. When transparency must be reduced (software Qt Quick renderer, or a component
// asks for it) every material has an opaque equivalent with the same contrast.
pragma Singleton
import QtQuick

QtObject {
    id: tokens

    // --- colour -----------------------------------------------------------------------
    readonly property QtObject color: QtObject {
        readonly property color graphite: "#0e1116"
        readonly property color midnight: "#0b1a2e"
        readonly property color deepBlue: "#12304f"
        readonly property color cyan: "#4fd1e8"
        readonly property color cyanBright: "#9ff3ff"
        readonly property color silver: "#c8d3de"
        readonly property color textPrimary: "#eef6fb"
        readonly property color textSecondary: "#a9b8c6"
        readonly property color textOnAccent: "#06202b"
        readonly property color ok: "#5fd39a"
        readonly property color warning: "#f2c46d"
        readonly property color critical: "#ff6b6b"
        readonly property color unknown: "#8d9aa8"
    }

    // --- opacity ----------------------------------------------------------------------
    readonly property QtObject opacity: QtObject {
        readonly property real regular: 0.62
        readonly property real elevated: 0.74
        readonly property real control: 0.18
        readonly property real controlHover: 0.28
        readonly property real controlPressed: 0.38
        readonly property real disabled: 0.4
    }

    // --- blur (applied by KWin, recorded here so the values have one home) --------------
    readonly property QtObject blur: QtObject {
        readonly property int kwinStrength: 12      // /etc/xdg/kwinrc [Effect-blur] BlurStrength
        readonly property int kwinNoise: 2          // [Effect-blur] NoiseStrength
        readonly property real contrast: 0.9        // Plasma style contrast effect
        readonly property real saturation: 1.4
    }

    // --- shape and space --------------------------------------------------------------
    readonly property QtObject radius: QtObject {
        readonly property int small: 8
        readonly property int medium: 12
        readonly property int large: 18
        readonly property int dock: 22
    }
    readonly property QtObject spacing: QtObject {
        readonly property int xs: 4
        readonly property int small: 8
        readonly property int medium: 12
        readonly property int large: 18
        readonly property int xl: 28
    }

    // --- typography -------------------------------------------------------------------
    readonly property QtObject type: QtObject {
        readonly property string family: "Noto Sans"
        readonly property int caption: 10
        readonly property int body: 11
        readonly property int title: 14
        readonly property int display: 20
        readonly property int weightRegular: Font.Normal
        readonly property int weightStrong: Font.DemiBold
    }

    // --- shadow -----------------------------------------------------------------------
    readonly property QtObject shadow: QtObject {
        readonly property color color: "#000000"
        readonly property real ambientOpacity: 0.28
        readonly property int ambientSpread: 10
        readonly property int offsetY: 4
    }

    // --- motion -----------------------------------------------------------------------
    readonly property QtObject motion: QtObject {
        readonly property int fast: 120         // hover, focus
        readonly property int medium: 200      // selection, small movement
        readonly property int slow: 320         // opening and closing surfaces
        readonly property int easing: Easing.OutCubic
        readonly property int easingExpand: Easing.OutBack
        readonly property real expandOvershoot: 1.2
    }

    // --- fallbacks --------------------------------------------------------------------
    // The software renderer has no shader effects and no compositor-side blur behind
    // translucent items, so translucency would only lower contrast.
    readonly property bool softwareRenderer: GraphicsInfo.api === GraphicsInfo.Software
    property bool reducedTransparency: softwareRenderer
    property bool reducedMotion: false

    function duration(ms) {
        return reducedMotion ? 0 : ms;
    }

    // --- materials --------------------------------------------------------------------
    function material(name) {
        const opaque = reducedTransparency;
        if (name === "elevated")
            return {
                fill: opaque ? color.deepBlue : Qt.rgba(0.07, 0.14, 0.24, opacity.elevated),
                border: Qt.rgba(0.62, 0.95, 1.0, opaque ? 0.35 : 0.22),
                highlight: Qt.rgba(1, 1, 1, opaque ? 0.0 : 0.10),
                shadowOpacity: shadow.ambientOpacity * 1.3
            };
        if (name === "control")
            return {
                fill: opaque ? "#1b2a3d" : Qt.rgba(0.62, 0.86, 1.0, opacity.control),
                border: Qt.rgba(0.62, 0.95, 1.0, opaque ? 0.30 : 0.18),
                highlight: Qt.rgba(1, 1, 1, opaque ? 0.0 : 0.08),
                shadowOpacity: 0
            };
        return {
            fill: opaque ? color.midnight : Qt.rgba(0.05, 0.09, 0.16, opacity.regular),
            border: Qt.rgba(0.62, 0.95, 1.0, opaque ? 0.30 : 0.16),
            highlight: Qt.rgba(1, 1, 1, opaque ? 0.0 : 0.07),
            shadowOpacity: shadow.ambientOpacity
        };
    }
}
