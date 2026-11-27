// Default desktop layout of AEGIS OS (first login of a new user), v3 hybrid desktop (M10).
//
// Two pieces of AEGIS Glass:
//
// The top bar: a thin translucent strip across the top of the screen. Left: the AEGIS
// mark (opens the launcher) and the name of the application in front, followed by that
// application's menus where it offers them (global menu). Right: search (Meta+S), the
// system tray (network, sound, notifications and the notification history), AEGIS Quick
// Settings (Meta+A) and the clock with the calendar.
//
// The dock: one floating panel, centred at the bottom and only as wide as its content,
// drawn by the AEGIS Glass theme (frosted, edge-lit; KWin blurs behind it in the Full
// and Balanced Glass profiles). It moves out of the way when a window would cover it
// ("dodge windows") and comes back when the pointer reaches the bottom edge. Plasma
// keeps both panels in place at every screen size. Contents: the launcher (Kickoff,
// Meta) with the AEGIS mark, pinned applications with running indicators (Meta+1…9),
// and the AEGIS Security status.

// --- top bar ---------------------------------------------------------------------------
const bar = new Panel();
bar.location = "top";
bar.height = 2 * Math.ceil((gridUnit * 1.7) / 2);
bar.floating = false;
bar.lengthMode = "fill";
bar.hiding = "none";
bar.opacity = "translucent";

bar.addWidget("org.aegisos.activewindow");
bar.addWidget("org.kde.plasma.appmenu");
bar.addWidget("org.kde.plasma.panelspacer");

const search = bar.addWidget("org.kde.milou");
search.globalShortcut = "Meta+S";

bar.addWidget("org.kde.plasma.systemtray");

const quick = bar.addWidget("org.aegisos.quicksettings");
quick.globalShortcut = "Meta+A";

const clock = bar.addWidget("org.kde.plasma.digitalclock");
clock.currentConfigGroup = ["Appearance"];
clock.writeConfig("showDate", true);
clock.writeConfig("dateFormat", "shortDate");
clock.writeConfig("dateDisplayFormat", "BesideTime");

// --- dock ------------------------------------------------------------------------------
const panel = new Panel();
panel.location = "bottom";
panel.height = 2 * Math.ceil((gridUnit * 3.4) / 2);
panel.floating = true;
panel.alignment = "center";
panel.lengthMode = "fit";
panel.hiding = "dodgewindows";
panel.opacity = "adaptive";

// (The Application Dashboard, org.kde.plasma.kickerdash, is not part of this Plasma
// build: CI run 45601312768 showed "Could not find requested component".)
const launcher = panel.addWidget("org.kde.plasma.kickoff");
launcher.currentConfigGroup = ["General"];
launcher.writeConfig("icon", "aegis-os");
launcher.writeConfig("favoritesDisplay", 0);
launcher.writeConfig("applicationsDisplay", 0);

const tasks = panel.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", [
    "applications:org.kde.dolphin.desktop",
    "applications:org.kde.konsole.desktop",
    "applications:systemsettings.desktop",
    "applications:org.aegisos.appearance.desktop",
]);
tasks.writeConfig("iconSpacing", 2);
tasks.writeConfig("indicateAudioStreams", true);

panel.addWidget("org.kde.plasma.marginsseparator");
panel.addWidget("org.aegisos.security");

for (const desktop of desktops()) {
    desktop.wallpaperPlugin = "org.kde.image";
    desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    desktop.writeConfig("Image", "file:///usr/share/wallpapers/AEGIS/");
}
