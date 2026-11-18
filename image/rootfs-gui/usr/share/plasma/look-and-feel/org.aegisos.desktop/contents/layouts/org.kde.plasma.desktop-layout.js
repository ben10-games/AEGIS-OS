// Default desktop layout of AEGIS OS (first login of a new user).
//
// One floating panel, centred at the bottom and only as wide as its content: the
// foundation of the future AEGIS dock. Launcher, pinned core applications, task
// manager, system tray, clock. The AEGIS wallpaper on every desktop.

const panel = new Panel();
panel.location = "bottom";
panel.height = 2 * Math.ceil(gridUnit * 2.5 / 2);
panel.floating = true;
panel.alignment = "center";
panel.lengthMode = "fit";
panel.hiding = "none";

panel.addWidget("org.kde.plasma.kickoff");
const tasks = panel.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", [
    "applications:org.kde.dolphin.desktop",
    "applications:org.kde.konsole.desktop",
    "applications:systemsettings.desktop",
]);
panel.addWidget("org.kde.plasma.marginsseparator");
panel.addWidget("org.kde.plasma.systemtray");
panel.addWidget("org.kde.plasma.digitalclock");

for (const desktop of desktops()) {
    desktop.wallpaperPlugin = "org.kde.image";
    desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    desktop.writeConfig("Image", "file:///usr/share/wallpapers/AEGIS/");
}
