conf_data = configuration_data()
conf_data.set('bindir', join_paths(get_option('prefix'), get_option('bindir')))

configure_file(
  input: 'com.felix.saxtune.desktop.in',
  output: 'com.felix.saxtune.desktop',
  configuration: conf_data,
  install: true,
  install_dir: get_option('datadir') / 'applications'
)

install_data('com.felix.saxtune.metainfo.xml',
  install_dir: get_option('datadir') / 'metainfo'
)

install_data('icons/com.felix.saxtune.png',
  install_dir: get_option('datadir') / 'icons/hicolor/512x512/apps'
)
