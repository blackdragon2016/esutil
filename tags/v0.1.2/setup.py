import sys,os
from distutils.core import setup

pyvers='%s.%s' % sys.version_info[0:2]
d1='lib/python%s/site-packages' % pyvers
d2='lib64/python%s/site-packages' % pyvers

if not os.path.exists('ups'):
    os.mkdir('ups')
tablefile=open('ups/esutil.table','w')
tablefile.write('setupOptional("python")\n');
tablefile.write('envPrepend(PYTHONPATH,${PRODUCT_DIR}/%s)\n' % d1)
tablefile.write('envPrepend(PYTHONPATH,${PRODUCT_DIR}/%s)\n' % d2)
tablefile.close()

# data_files copies the ups/esutil.table into prefix/ups
setup(name='esutil',
      version='0.1',
      description='Erin Sheldons Utilities',
      packages=['esutil'],
      data_files=[('ups',['ups/esutil.table'])])