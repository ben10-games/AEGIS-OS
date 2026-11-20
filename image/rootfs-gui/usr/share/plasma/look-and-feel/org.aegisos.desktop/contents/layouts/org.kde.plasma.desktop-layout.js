// Default desktop layout of AEGIS OS (first login of a new user), GUI v1.
//
// The AEGIS dock: one floating, translucent panel, centred at the bottom and only as
// wide as its content. KWin blurs the wallpaper behind it (/etc/xdg/kwinrc). Contents:
// the launcher with the AEGIS mark, pinned core applications with running indicators,
// the AEGIS Security status, the system tray (network, volume, power) and the clock.

const panel = new Panel();
panel.location = "bottom";
panel.height = 2 * Math.ceil(gridUnit * 3 / 2);
panel.floating = true;
panel.alignment = "center";
panel.lengthMode = "fit";
panel.hiding = "none";
panel.opacity = "translucent";

const kickoff = panel.addWidget("org.kde.plasma.kickoff");
kickoff.currentConfigGroup = ["General"];
kickoff.writeConfig("icon", "aegis-os");
kickoff.writeConfig("favoritesDisplay", 0);

const tasks = panel.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", [
    "applications:org.kde.dolphin.desktop",
    "applications:org.kde.konsole.desktop",
    "applications:systemsettings.desktop",
]);
tasks.writeConfig("iconSpacing", 2);

panel.addWidget("org.kde.plasma.marginsseparator");
panel.addWidget("org.aegisos.security");
panel.addWidget("org.kde.plasma.systemtray");
panel.addWidget("org.kde.plasma.digitalclock");

for (const desktop of desktops()) {
    desktop.wallpaperPlugin = "org.kde.image";
    desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    desktop.writeConfig("Image", "file:///usr/share/wallpapers/AEGIS/");
}
