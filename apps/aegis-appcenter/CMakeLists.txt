qt_add_executable(aegis-appcenter main.cpp)
qt_add_qml_module(aegis-appcenter
    URI AegisAppCenter
    VERSION 1.0
    QML_FILES Main.qml AppCard.qml Details.qml
)
target_link_libraries(aegis-appcenter PRIVATE
    Qt6::Core Qt6::Gui Qt6::Qml Qt6::Quick Qt6::QuickControls2 Qt6::DBus)
install(TARGETS aegis-appcenter RUNTIME DESTINATION bin)
install(FILES org.aegisos.appcenter.desktop DESTINATION share/applications)
install(FILES aegis-appcenter-updates.service aegis-appcenter-updates.timer
        DESTINATION lib/systemd/user)
