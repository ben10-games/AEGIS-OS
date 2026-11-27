qt_add_executable(aegis-welcome main.cpp)
qt_add_qml_module(aegis-welcome
    URI AegisWelcome
    VERSION 1.0
    QML_FILES
        Main.qml
        Glass.qml
        AegisMark.qml
        Step.qml
        scenes/Awakens.qml
        scenes/Desktop.qml
        scenes/Workspace.qml
        scenes/MakeItYours.qml
        scenes/Apps.qml
        scenes/Security.qml
        scenes/Ready.qml
)
target_link_libraries(aegis-welcome PRIVATE
    Qt6::Core Qt6::Gui Qt6::Qml Qt6::Quick Qt6::QuickControls2 Qt6::DBus)
install(TARGETS aegis-welcome RUNTIME DESTINATION bin)
install(FILES watch.js DESTINATION share/aegis/welcome)
install(FILES org.aegisos.welcome.desktop DESTINATION share/applications)
