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

foreach size : ['16x16', '32x32', '48x48', '64x64', '128x128', '256x256', '512x512']
  install_data('icons/@0@/com.felix.saxtune.png'.format(size),
    install_dir: get_option('datadir') / 'icons/hicolor' / size / 'apps'
  )
endforeach

gnome = import('gnome')
gnome.post_install(
  gtk_update_icon_cache: true,
  update_desktop_database: true,
)
