import sys
def configuration(parent_package='',top_path=None):
    from numpy.distutils.misc_util import Configuration
    config = Configuration('esutil',parent_package,top_path)

    # this requires a fortran 95 compiler
    config.add_subpackage('cosmology')

    config.add_subpackage('ccosmo')

    config.add_subpackage('stat')
    config.add_subpackage('htm')
    config.add_subpackage('integrate')
    config.add_subpackage('recfile')
    config.add_subpackage('pyfitspatch')

    return config

if __name__ == '__main__':
    print('This is the wrong setup.py file to run')
