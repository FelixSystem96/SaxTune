python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').path())
conf.set('pkgdatadir', join_paths(get_option('prefix'), get_option('datadir'), meson.project_name()))
conf.set('localedir', join_paths(get_option('prefix'), get_option('localedir')))

configure_file(
  input: 'saxtune.in',
  output: 'saxtune',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)

saxtune_sources = [
  'saxtune/__init__.py',
  'saxtune/main.py',
  'saxtune/ui.py',
  'saxtune/audio.py',
  'saxtune/config.py',
  'saxtune/mpris.py',
]

pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
moduledir = join_paths(pkgdatadir, 'saxtune')

install_data(saxtune_sources, install_dir: moduledir)
