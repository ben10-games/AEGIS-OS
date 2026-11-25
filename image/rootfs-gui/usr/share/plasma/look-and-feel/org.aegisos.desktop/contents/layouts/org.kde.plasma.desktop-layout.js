// Default desktop layout of AEGIS OS (first login of a new user), GUI v2.
//
// The AEGIS dock: one floating panel, centred at the bottom and only as wide as its
// content, drawn by the AEGIS Glass theme (frosted, edge-lit; KWin blurs behind it in the
// Full and Balanced Glass profiles). It moves out of the way when a window would cover
// it ("dodge windows") and comes back when the pointer reaches the bottom edge. Plasma
// keeps it centred and at the bottom at every screen size.
//
// Contents: the launcher (Kickoff: a glass popup with search, favourites in a grid, all
// applications and keyboard navigation) with the AEGIS mark, pinned applications
// with running indicators, the AEGIS Security status, the system tray (network, volume,
// quick settings) and the clock.

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
panel.addWidget("org.kde.plasma.systemtray");
panel.addWidget("org.kde.plasma.digitalclock");

for (const desktop of desktops()) {
    desktop.wallpaperPlugin = "org.kde.image";
    desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    desktop.writeConfig("Image", "file:///usr/share/wallpapers/AEGIS/");
}
