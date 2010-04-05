license="""
  Copyright (C) 2010  Erin Sheldon

    This program is free software; you can redistribute it and/or modify it
    under the terms of version 2 of the GNU General Public License as
    published by the Free Software Foundation.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""


import subprocess
from sys import stdout, stderr


def colprint(*args, **keys):
    """
    Name:
        colprint
    Purpose:
        print the input sequences or arrays in columns.  All must be the
        same length.
    Calling Sequence:
        colprint(var1, var2, ..., nlines=all, sep=' ', file=None)

    Inputs:
        A set of python objects.  Each must be a sequence or array and all must
        be the same length.

    Optional Inputs:
        nlines:  Number of lines to print.  Default is all.
        sep: Separator, default is ' '
        file:  A file path or file object.  Default is to print to standard
            output.

    Revision History:
        Create: 2010-04-05, Erin Sheldon, BNL
    """
    nargs = len(args)
    if nargs == 0:
        return

    try:
        n1 = len(args[0])
    except:
        raise ValueError("Could not get len() of argument 1")

    if 'nlines' in keys:
        nlines = keys['nlines']
        if nlines > n1:
            nlines = n1
    else:
        nlines = n1

    if 'sep' in keys:
        sep=keys['sep']
    else:
        sep=' '

    if 'file' in keys:
        f = keys['file']
        if isinstance(f, file):
            fobj = f
        else:
            fobj = open(f,'w')
    else:
        fobj = stdout

    for i in range(nargs):
        try:
            l=len(args[i])
        except:
            raise ValueError("Could not get len() of argument %s" % (i+1))
        if l != n1:
            e="argument %s has non-matching length.  %s instead of %s" \
                    % (i+1, l, n1)
            raise ValueError(e)

    format = ['%s']*nargs
    format = sep.join(format)
    for i in range(nlines):
        data = []
        for iarg in range(nargs):
            data.append(args[iarg][i])
        
        data = tuple(data)

        line = format % data
        fobj.write(line)
        fobj.write("\n")

    if fobj != stdout:
        fobj.close()


def ptime(seconds, fobj=None, format='%s\n'):
    """
    Name:
        ptime(seconds, fobj=None, format='%s\n')
    Purpose:
        Print a pretty version of the input seconds.  
    Calling Sequence:
        ptime(seconds, fobj=None, format='%s\n')
    
    Inputs:
        Time in seconds.

    Optional Inputs:
        fobj: A file object in which to write the result.
        format: The format for printing.  The default is '%s\n'

    Examples:
        import time
        tm1=time.time()
        ...do somethign
        tm2=time.time()
        ptime(tm2-tm1)

        5 min 23.210000 sec
    """

    min, sec = divmod(seconds, 60.0)
    hr, min = divmod(min, 60.0)
    days, hr = divmod(hr, 24.0)
    yrs,days = divmod(days, 365.0)

    if yrs > 0:
        tstr="%d years %d days %d hours %d min %f sec" % (yrs,days,hr,min,sec)
    elif days > 0:
        tstr="%d days %d hours %d min %f sec" % (days,hr,min,sec)
    elif hr > 0:
        tstr="%d hours %d min %f sec" % (hr,min,sec)
    elif min > 0:
        tstr="%d min %f sec" % (min,sec)
    else:
        tstr="%f sec" % sec

    if fobj is None:
        stdout.write(format % tstr)
    else:
        fobj.write(format % tstr)


def exec_process(command, 
                 timeout=None, 
                 stdout_file=subprocess.PIPE, 
                 stderr_file=subprocess.PIPE, 
                 shell=True,
                 verbose=False):
    """
    Name:
        execute_command
    Purpose:
        Execute a command on the operating system with a possible timeout in
        seconds
    
    Calling Sequence:

        exit_status, stdout_returned, stderr_returned = \
           execute_command(command, 
                           timeout=None, 
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE, 
                           shell=True,
                           verbose=False)

    """

    # the user can send file names, PIPE, or a file object
    if isinstance(stdout_file, str):
        stdout_fileobj = open(stdout_file, 'w')
    else:
        stdout_fileobj=stdout_file

    if isinstance(stderr_file, str):
        stderr_fileobj = open(stderr_file, 'w')
    else:
        stderr_fileobj = stderr_file


    # if a list was entered, convert to a string.  Also print the command
    # if requested
    if verbose:
        stdout.write('Executing command: \n')
    if isinstance(command, list):
        cmd = ' '.join(command)
        if verbose:
            stdout.write(command[0] + '    \\\n')
            for c in command[1:]:
                stdout.write('    '+c+'    \\\n')
        #print 'actual cmd:',cmd
    else:
        cmd=command
        if verbose:
            stdout.write('%s\n' % cmd)



    stdout.flush()
    stderr.flush()
    pobj = subprocess.Popen(cmd, 
                            stdout=stdout_fileobj, 
                            stderr=stderr_fileobj, 
                            shell=shell)

    if timeout is not None:
        exit_status, stdout_ret, stderr_ret = _poll_subprocess(pobj, timeout)
    else:
        # this just waits for the process to end
        stdout_ret, stderr_ret = pobj.communicate()
        # this is not set until we call pobj.communicate()
        exit_status = pobj.returncode

    # If they were opened files, close them
    if isinstance(stdout_fileobj, file):
        stdout_fileobj.close()
    if isinstance(stderr_fileobj, file):
        stderr_fileobj.close()

    return exit_status, stdout_ret, stderr_ret

def dict_select(input_dict, keep=None, remove=None):
    """
    Name:
        dict_select
    Purpose:
        Select a subset of keys from the input dict.

    Calling Sequence:
        newdict = dict_select(input_dict, keep=all, remove=[])

    Inputs:
        dict: the input dictionary.

    Optional Inputs:
        keep=None: 
            A list of keys to keep. If the input is None or [] all keys are
            returned that are not in the remove list.  Default [].

        remove=None: 
            A list of keys to ignore.  Defaults to [].

    """

    outdict={}

    if keep is None:
        keep = []
    if remove is None:
        remove = []

    if len(keep) == 0:
        # wrap in list() for py3k in which keys() does not return a list.
        keep = list( input_dict.keys() )

    for key in keep:
        if key in input_dict and key not in remove:
            outdict[key] = input_dict[key]

    return outdict

