// Welcome to AEGIS (v3, M11): KWin script that reports real window events to the tour
// (org.aegisos.Welcome on the session bus) so its exercises complete on what the user
// really does. Read-only towards other windows: it only reads their class, geometry and
// state. It keeps the tour's own window above the others so it stays visible while the
// user practises on a real window. Loaded and unloaded by aegis-welcome.
function report(event, window) {
    if (!window)
        return;
    const g = window.frameGeometry;
    const a = workspace.clientArea(KWin.MaximizeArea, window);
    callDBus("org.aegisos.Welcome", "/Welcome", "org.aegisos.Welcome", "report",
        JSON.stringify({
            event: event,
            cls: String(window.resourceClass),
            x: Math.round(g.x), y: Math.round(g.y),
            w: Math.round(g.width), h: Math.round(g.height),
            ax: Math.round(a.x), ay: Math.round(a.y),
            aw: Math.round(a.width), ah: Math.round(a.height),
            minimized: window.minimized,
            normal: window.normalWindow,
            transient: !!window.transient,
            popup: !!(window.popupWindow || window.dropdownMenu || window.popupMenu),
            // On Wayland the class is the application ID: "org.kde.plasmashell".
            plasma: String(window.resourceClass).indexOf("plasmashell") >= 0
                && !window.dock && !window.tooltip && !window.notification
                && !window.onScreenDisplay
        }));
}

function watch(window) {
    if (String(window.resourceClass) === "org.aegisos.welcome")
        window.keepAbove = true;
    window.frameGeometryChanged.connect(function () { report("geometry", window); });
    window.minimizedChanged.connect(function () { report("minimized", window); });
}

workspace.windowAdded.connect(function (window) {
    watch(window);
    report("added", window);
});
workspace.windowActivated.connect(function (window) { report("activated", window); });
for (const window of workspace.windowList())
    watch(window);
