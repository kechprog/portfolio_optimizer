# PyInstaller hook for scipy
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Collect all scipy submodules
hiddenimports = collect_submodules('scipy')

# Ensure critical sparse modules are included
hiddenimports += [
    'scipy._cyutility',
    'scipy.sparse._csparsetools',
    'scipy.sparse._sparsetools',
    'scipy._lib.messagestream',
]

# Collect data files
datas = collect_data_files('scipy')