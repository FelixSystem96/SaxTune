conf_data = configuration_data()
conf_data.set('bindir', join_paths(get_option('prefix'), get_option('bindir')))

configure_file(
  input: 'io.github.felixsystem96.SaxTune.desktop.in',
  output: 'io.github.felixsystem96.SaxTune.desktop',
  configuration: conf_data,
  install: true,
  install_dir: get_option('datadir') / 'applications'
)

install_data('io.github.felixsystem96.SaxTune.metainfo.xml',
  install_dir: get_option('datadir') / 'metainfo'
)

install_data('icons/scalable/io.github.felixsystem96.SaxTune.svg',
  install_dir: get_option('datadir') / 'icons/hicolor/scalable/apps'
)

gnome = import('gnome')
gnome.post_install(
  gtk_update_icon_cache: true,
  update_desktop_database: true,
)
