"""
Utilities for using and manipulating numerical python arrays (NumPy).

    ahelp(array, recurse=False, pretty=True)
        Print out a formatted description of the input array.   If the array
        has fields, individual descriptions are printed for each field.  This
        is designed to be similar to help, struct, /str in IDL. 


    aprint(arr, fields=None, nlines=None, format=None)
        Print fields from the array in columns.

    arrscl(arr, minval, maxval, arrmin=None, arrmax=None)
        Rescale the range of an array to be between minval and maxval.

    make_xy_grid(npoints, xrange, yrange)
        Create a grid of x-y points, returning x and y as numpy arrays.

    combine_arrlist(list_of_arrays, keep=False)
        Combine the list of arrays into one big array.  Arrays must all have
        the same datatype.

    copy_fields(array1, array2)
        Copy common fields from one numpy array to another.  The name 
        matching is case senitive.

    extract_fields(array, names, strict=True)

        Extract a set of fields from a numpy array.  A new array is returned
        with the requested fields and data copied in.  The name matching is
        case sensitive.

    remove_fields(array, names)
        Remove a set of fields from the array.  A new array is returned
        with the leftover fields and data copied in.  The name matching 
        is case sensitive.

    add_fields(arr, dtype_or_descr, defaults=None)
        Create a new array with fields from the input array and new
        fields as indicated by the input numpy type descriptor.
        The data are copied from the original array.


    reorder_fields(arr, ordered_names, strict=True)
        Re-order the fields according the the listed names.  Names not in the
        list are put at the end.


    copy_fields_by_name(arr, names, values)
        Copy values into a numpy array by field name.


    split_fields(array, fields=None, getnames=False)

         Get a tuple of references to the individual fields in a structured
         array (aka recarray).  If fields= is sent, just return those fields.
         If getnames=True, return a tuple of the names extracted also.



    compare_arrays(array1, array2, ignore_missing=True, verbose=False)
        Compare the values field-by-field in two sets of numpy arrays or
        recarrays.  Return true if the data match.


    is_big_endian(array)
        Return True if array is big endian.  Note strings are neither big
        or little endian.  The input must be a simple numpy array, not
        an array with fields.

    is_little_endian(array)
        Return True if array is little endian. Note strings are neither big
        or little endian.  The input must be a simple numpy array, not
        an array with fields.



    to_big_endian(array, inplace=False, keep_dtype=False)
        Convert an array to big endian byte order, updating the dtype to
        reflect this.  The array can have fields. 
    to_little_endian(array, inplace=False, keep_dtype=False)
        Convert an array to little endian byte order, updating the dtype to
        reflect this.  The array can have fields.  
    to_native(array, inplace=False, keep_dtype=False)
        Convert an array to native byteorder, updating the dtype to
        reflect this.  The array can have fields.  

    byteswap(array, inplace=False, keep_dtype=False)
        Chance the byte order of an array, updating the dtype to reflect this.
        The array can have fields.   This is a wrapper for the .byteswap()
        method which does not update the dtype to reflect the new byte
        ordering.

    unique(arr, values=False)
        Return indices of unique elements of a numpy array, or optionally
        the unique values.  This is not order preserving.  This is currently
        implemented in a slow fashion, should be updated.

    match(arr1, arr2)
        match two numpy arrays.  Return the indices of the matches or [-1] if
        no matches are found.  This means arr1[ind1] == arr2[ind2] is true for
        all corresponding pairs. Arrays must contain only unique elements


    dict2array(dict, sort=False, keys=None)
        Convert a dictionary to a numpy array.  Works for simple typs such as
        strings, integers, floating.

    splitarray(nper, array)
        Split up an array into chunks of at least a given size.  Return a
        list of these subarrays.  The ordering is perserved.

 
    randind(nmax, nrand)
        Return nrand random indices, with replacement, in the open 
        range [0,nmax)


""" 

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




import sys
from sys import stdout, stderr
import copy
import stat
import esutil

try:
    import numpy
    have_numpy=True
except:
    have_numpy=False


def ahelp(array, recurse=False, pretty=True, index=0):
    """
    Name:
      ahelp()

    Purpose:
        Print out a formatted description of the input array.   If the array
        has fields, individual descriptions are printed for each field.  This
        is designed to be similar to help, struct, /str in IDL. 

    Calling Sequence:
        ahelp(array, recurse=False, pretty=True)
    
    Inputs:
        array: A numpy array.

    Optional Inputs:
        recurse: for sub-arrays with fields, print out a full description. 
            default is False.
        pretty:  If True, split field descriptions onto multiple lines if
            the name is longer than 15 characters.  Nicer for the eye, but
            harder for a machine to parse.  Also, strings are surrounded
            by quotes 'string'.  Default is True.[:w

    Example:
        ahelp(a)
        size: 1147506  nfields: 27  type: records
          run                >i4  1933
          rerun              |S3  '157'
          camcol             >i2  1
          field              >i4  11
          mjd                >i4  51886
          tai                >f8  array[5]
          ra                 >f8  102.905870701
          dec                >f8  -1.05070432844

    Revision History:
        Created: 2010-04-05, Erin Sheldon, BNL 

    """


    if not hasattr(array, 'dtype'):
        raise ValueError("input must be an array")

    names = array.dtype.names
    descr = array.dtype.descr

    topformat="size: %s  nfields: %s  type: %s\n"

    if names is None:
        type=descr[0][1]
        nfields=0 
        line=topformat % (array.size, nfields, type)
        stdout.write(line)

    else:
        line=topformat % (array.size, len(names), 'records')
        stdout.write(line)
        _print_field_info(array, recurse=recurse, pretty=pretty, index=index)

           

def _print_field_info(array, nspace=2, recurse=False, pretty=True, index=0):
    names = array.dtype.names
    if names is None:
        raise ValueError("array has no fields")

    spacing = ' '*nspace

    nname = 15
    ntype = 6

    # this format makes something machine readable
    format = spacing + "%-" + str(nname) + "s %" + str(ntype) + "s  %s\n"
    # this one is prettier since lines wrap after long names
    pformat = spacing + "%-" + str(nname) + "s\n %" + str(nspace+nname+ntype) + "s  %s\n"

    max_pretty_slen = 25
    
    for i in range(len(names)):

        hasfields=False


        n=names[i]

        type=array.dtype.descr[i][1]

        fdata = array[n][index]

        shape_str = ','.join( str(s) for s in fdata.shape)

        if fdata.dtype.names is not None:
            type = 'rec[%s]' % shape_str
            d=''
            hasfields=True
        elif numpy.isscalar(fdata):
            if isinstance(fdata, numpy.string_):
                d=fdata

                # if pretty printing, reduce string lengths
                if pretty and len(d) > max_pretty_slen:
                    d = fdata[0:max_pretty_slen]
                    d = "'" + d +"'"
                    d = d+'...'
                else:
                    if pretty:
                        d = "'" + d +"'"
            else:
                d = fdata
        else:
            d = 'array[%s]' % shape_str
        
        if pretty and len(n) > 15:
            l = pformat % (n,type,d)
        else:
            l = format % (n,type,d)
        stdout.write(l)

        if hasfields and recurse:
            new_nspace = nspace + nname + 1 + ntype + 2
            _print_field_info(array[n], nspace=new_nspace, recurse=recurse)


def aprint(arr, fields=None, nlines=None, format=None):
    if fields is None:
        fields = arr.dtype.names

    ftup = split_fields(arr, fields=fields)

    colprint =esutil.misc.colprint

    command = 'colprint('
    arglist=[]
    for i in range(len(fields)):
        arglist.append('ftup[%s]' % i)

    arglist = ', '.join(arglist)
    command = 'colprint('+arglist+', nlines=nlines,format=format,names=fields)'
    eval(command)


def arrscl(arr, minval, maxval, arrmin=None, arrmax=None):
    """
    NAME:
      arrscl()

    CALLING SEQUENCE:
      newarr = arrscl(arr, minval, maxval, arrmin=None, arrmax=None)

    PURPOSE:
      Rescale the range of an array to be between minval and maxval.
    
    INPUTS:
      arr: An array
      minval: The minimum value for the output array
      maxval: The maximum value for the output array

    OPTIONAL OUTPUTS:
      arrmin=None: An number to use for the min range of the input array. By
        default it is taken from the input array.
      arrmax=None: An number to use for the max range of the input array. By
        default it is taken from the input array.

      * arrmin,arrmax are useful if you know the array is a sample of a
        particular range, for example of they are random numbers drawn
        from [0,1] you would send arrmin=0., arrmax=1.

    OUTPUTS:
      The new array.

    REVISION HISTORY:
      Converted from IDL: 2006-10-23. Erin Sheldon, NYU
      
    """

    # makes a copy either way (asarray would not if it was an array already)
    output = numpy.array(arr)
    
    if arrmin == None: arrmin = output.min()
    if arrmax == None: arrmax = output.max()
    
    if output.size == 1:
        return output
    
    if (arrmin == arrmax):
        raise ValueError('arrmin must not equal arrmax')

    #try:
    a = (maxval - minval)/(arrmax - arrmin)
    b = (arrmax*minval - arrmin*maxval)/(arrmax - arrmin)
    #except:
    #print "Error calculating a,b: ", \
    #      sys.exc_info()[0], sys.exc_info()[1]
    #return None

    # in place
    numpy.multiply(output, a, output)
    numpy.add(output, b, output)
    
    return output

def make_xy_grid(n, xrang, yrang):
    """
    NAME:
        make_xy_grid()

    CALLING SEQUENCE:
        x,y = make_xy_grid(npoints, xrange, yrange)

    PURPOSE
        Create a grid of x-y points, returning x and y as numpy arrays.

    REVISION HISTORY:
        Created: mid 2009, Erin Sheldon, BNL
    """

    rng = numpy.arange(n, dtype='f8')
    ones = numpy.ones(n, dtype='f8')

    x = arrscl(rng, xrang[0], xrang[1])
    y = arrscl(rng, yrang[0], yrang[1])

    x= numpy.outer(x, ones)
    y= numpy.outer(ones, y)
    x = x.flatten(1)
    y = y.flatten(1)

    return x,y

def combine_arrlist(arrlist, keep=False):
    """
    NAME:
        combine_arrlist

    CALLING SEQUENCE:
        arr = combine_arrlist(list_of_arrays, keep=False)

    PURPOSE:
        Combined the list of arrays into one big array.  The arrays must all
        be the same data type.

    KEYWORDS:
        keep:  By default the elements are deleted as they are added to the 
            big array.  Turn this off with keep=True

    REVISION HISTORY:
        Inspired by combine_ptrlist from SDSSIDL.  2007.  Erin Sheldon, BNL 
    """
    if not isinstance(arrlist,list):
        raise RuntimeError('Input must be a list of arrays')

    isarray = isinstance(arrlist[0], numpy.ndarray)
    isrec = isinstance(arrlist[0], numpy.recarray)
        
    if not isarray:
        mess = 'Input must be a list of arrays or recarrays. Found %s' % \
                type(arrlist[0])
        raise RuntimeError(mess)

    # loop and get total number of entries
    counts=0
    for data in arrlist:
        counts = counts+data.size

    output = numpy.zeros(counts, dtype=arrlist[0].dtype)
    if isrec:
        output = output.view(numpy.recarray)

    beg=0
    if keep:
        for data in arrlist:
            num = data.size
            output[beg:beg+num] = data
            beg=beg+num
    else:
        while len(arrlist) > 0:
            data = arrlist.pop(0)
            num = data.size
            output[beg:beg+num] = data
            del data
            beg=beg+num

    return output


def copy_fields(arr1, arr2):
    """
    NAME:
        copy_fields

    CALLING SEQUENCE:
        copy_fields(array1, array2)

    PURPOSE:
        Copy common fields from one numpy array to another.  The name 
        matching is case senitive.

    REVISION HISTORY:
        Inspired by struct_assign in IDL.  2007 Erin Sheldon, BNL.

    """
    if arr1.size != arr2.size:
        raise ValueError('arr1 and arr2 must be the same size')

    names1=arr1.dtype.names
    names2=arr2.dtype.names

    for name in names1:
        if name in names2:
            arr2[name] = arr1[name]

def extract_fields(arr, keepnames, strict=True):
    """
    NAME:
        extract_fields

    CALLING SEQUENCE:
        newarr = extract_fields(arr, names, strict=True)

    PURPOSE:
        Extract a set of fields from a numpy array.  A new array is returned
        with the requested fields and data copied in.  The name matching is
        case sensitive.

        The order of the fields is the order in the original array.

    Inputs:
        arr: A numpy structure, or array with fields.
        names: The subset of names to extract.  

    Optional Inputs:
        strict: 
            If True, requested names that are not found in the input array will
            raise a ValueError.  Default is True.

    REVISION HISTORY:
        Created 2007, Erin Sheldon, NYU.
        Added strict keyword, 2010-04-07, Erin Sheldon, BNL
    """
    if not isinstance(keepnames, (tuple,list,numpy.ndarray)):
        keepnames = [keepnames]

    arrnames = list( arr.dtype.names )

    if strict:
        for name in keepnames:
            if name not in arrnames:
                raise ValueError("field not found: %s" % name)

    new_descr = []
    for d in arr.dtype.descr:
        name=d[0]
        if name in keepnames:
            new_descr.append(d)

    if len(new_descr) == 0:
        raise ValueError('No fields kept')

    shape = arr.shape
    new_arr = numpy.zeros(shape,dtype=new_descr)
    copy_fields(arr, new_arr)
    return new_arr








def remove_fields(arr, rmnames):
    """
    NAME:
        remove_fields

    CALLING SEQUENCE:
        newarr = remove_fields(arr, names)

    PURPOSE:
        Remove a set of fields from the array.  A new array is returned
        with the leftover fields and data copied in.  The name matching 
        is case sensitive.

    REVISION HISTORY:
        Created 2007, Erin Sheldon, NYU.
    """
    if type(rmnames) != list:
        rmnames=[rmnames]
    descr = arr.dtype.descr
    new_descr = []
    for d in descr:
        name=d[0]
        if name not in rmnames:
            new_descr.append(d)

    if len(new_descr) == 0:
        raise ValueError('Error: All fields would be removed')

    shape = arr.shape
    new_arr = numpy.zeros(shape, dtype=new_descr)
    copy_fields(arr, new_arr)
    return new_arr

def add_fields(arr, add_dtype_or_descr, defaults=None):
    """
    NAME:
        add_fields

    CALLING SEQUENCE:
        newarr = add_fields(arr, dtype_or_descr, defaults=None)

    PURPOSE:
        Create a new array with fields from the input array and new
        fields as indicated by the input numpy dtype or descr object.
        Return a new array with the data copied from the original array.

    KEYWORDS:
        defaults:  By default the new fields are zeroed.  Send this keyword
            to add default values to the fields.  Must be the same length
            as the input type descriptor.

    REVISION HISTORY:
        Created 2007, Erin Sheldon, NYU.


    """
    # the descr is a list of tuples
    old_descr = arr.dtype.descr
    add_dtype = numpy.dtype(add_dtype_or_descr)
    add_descr = add_dtype.descr

    new_descr = copy.deepcopy(old_descr)

    old_names = list(arr.dtype.names)
    new_names = list(add_dtype.names)
    for d in add_descr:
        name=d[0]
        if old_names.count(name) ==0:
            new_descr.append(d)
        else:
            raise ValueError( 'field '+str(name)+' already exists')

    shape = arr.shape
    new_arr = numpy.zeros(shape, dtype=new_descr)
    
    copy_fields(arr, new_arr)
    
    # See if the user has indicated default values for the new fields
    if defaults is not None:
        if type(defaults) != list:
            defaults=[defaults]
        if len(defaults) != len(add_descr):
            raise ValueError('defaults must be same length as new dtype')
        copy_fields_by_name(new_arr, list(add_dtype.names), defaults)

    return new_arr


def reorder_fields(arr, ordered_names, strict=True):
    """
    NAME:
        reorder_fields

    CALLING SEQUENCE:
        newarr = reorder_fields(arr, ordered_names, strict=True)

    PURPOSE:
        Re-order the fields according the the listed names.  Names
        not in the list are put at the end.


    Inputs:
        arr: A numpy structure, or array with fields.
        ordered_names: The ordered subset of names.  These are placed in order
            at the front.  Non-matching names are placed at the back.

    Optional Inputs:
        strict: 
            If True, requested names that are not found in the input array will
            raise a ValueError.  Default is True.

    REVISION HISTORY:
        Created 2007, Erin Sheldon, NYU.
        Added strict keyword, 2010-04-07, Erin Sheldon, BNL
    """

    if not isinstance(ordered_names, (tuple,list,numpy.ndarray)):
        ordered_names = [ordered_names]

    # this is so we can get indices
    original_names = numpy.array( arr.dtype.names )
    original_descr = arr.dtype.descr

    new_names = []
    new_descr = []

    for name in ordered_names:
        w, = numpy.where( original_names == name )
        if w.size != 0:
            new_names.append(name)
            new_descr.append( original_descr[w[0]] )
        else:
            if strict:
                raise ValueError("field not found: '%s'" % name)
    
    # now put in the remaining names in original order at the back
    for i in range(original_names.size):
        name = original_names[i]
        if name not in new_names:
            new_names.append(name)
            new_descr.append(original_descr[i])

    shape = arr.shape
    new_arr = numpy.zeros(shape,dtype=new_descr)
    copy_fields(arr, new_arr)
    return new_arr




def copy_fields_by_name(arr, names, vals):
    """
    NAME:
        copy_fields_by_name

    CALLING SEQUENCE:
        copy_fields_by_name(arr, names, values)

    PURPOSE:
        Copy values into a numpy array by field name.

    INPUTS:
        names:  Field names to be copied, scalar or sequence.
        values: The values to be copied into each field.  These values
            can be in a sequence of the same length as names.   They
            must either be scalars or their shape must match the underlying
            structure of the field.

    EXAMPLES:
        names=['x','flux', 'source']
        values=[x_array, flux_array, name_scalar]
        copy_fields_by_name(arr, names, values)

    REVISION HISTORY:
        Created 2007, Erin Sheldon, NYU.

    """
    if type(names) != list and type(names) != numpy.ndarray:
        names=[names]
    if type(vals) != list and type(vals) != numpy.ndarray:
        vals=[vals]
    if len(names) != len(vals):
        raise ValueError('Length of names and values must be the same')

    arrnames = list(arr.dtype.names)
    for name,val in zip(names,vals):
        if name in arrnames:
            arr[name] = val


def split_fields(data, fields=None, getnames=False):
    """
    Name:
        split_fields

    Calling Sequence:
        The standard calling sequence is:
            field_tuple = split_fields(data, fields=)
            f1,f2,f3,.. = split_fields(data, fields=)

        You can also return a list of the extracted names
            field_tuple, names = split_fields(data, fields=, getnames=True)

    Purpose:
        Get a tuple of references to the individual fields in a structured
        array (aka recarray).  If fields= is sent, just return those
        fields.  If getnames=True, return a tuple of the names extracted
        also.

        If you want to extract a set of fields into a new structured array
        by copying the data, see esutil.numpy_util.extract_fields

    Inputs:
        data: An array with fields.  Can be a normal numpy array with fields
            or the recarray or another subclass.
    Optional Inputs:
        fields: A list of fields to extract. Default is to extract all.
        getnames:  If True, return a tuple of (field_tuple, names)

    """

    outlist = []
    allfields = data.dtype.fields

    if allfields is None:
        if fields is not None:
            raise ValueError("Could not extract fields: data has "
                             "no fields")
        return (data,)
    
    if fields is None:
        fields = allfields
    else:
        if isinstance(fields, (str,unicode)):
            fields=[fields]

    for field in fields:
        if field not in allfields:
            raise ValueError("Field not found: '%s'" % field)
        outlist.append( data[field] )

    output = tuple(outlist)
    if getnames:
        return output, fields
    else:
        return output





def compare_arrays(arr1, arr2, verbose=False, ignore_missing=True):
    """
    NAME:
        compare_arrays

    CALLING SEQUENCE:
        boolval=compare_arrays(array1, array2, ignore_missing=True,
                               verbose=False)

    PURPOSE:
        Compare the values field-by-field in two sets of numpy arrays or
        recarrays.  Return true if the data match.

    INPUTS:
        array1, array2: Two arrays with fields.

    KEYWORDS:
        ignore_missing: Default True.  Ignore fields not found in both
            arrays.
        verbose:  By default the program is silent.  set verbose=True to
            print info about each field.

    OUTPUTS:
        True if the matching criteria are met, False if not.

    REVISION HISTORY:
        Created 2007, Erin Sheldon, NYU.
        Added ignore_missing keyword.  2009-11-02, Erin Sheldon, BNL

    """

    nfail = 0

    # If requested, check the arrays have exactly the same names.
    if not ignore_missing:
        # make sure the name lists match
        if verbose:
            stdout.write("    Matching names........")

        for n in arr1.dtype.names:
            if n not in arr2.dtype.names:
                nfail += 1
                if verbose:
                    stdout.write("\n        Field '%s' found only in "
                                 "array1" % n)
        for n in arr2.dtype.names:
            if n not in arr1.dtype.names:
                nfail += 1
                if verbose:
                    stdout.write("\n        Field '%s' found only in "
                                 "array2" % n)

        if verbose:
            if nfail == 0:
                stdout.write("OK")
            stdout.write("\n")

    else:
        if verbose:
            stdout.write("    Not checking that all fields names match\n")


    # Compare the data for matchine names
    for n in arr1.dtype.names:
        if n in arr2.dtype.names:
            # the field was found, let's see if the data match
            if verbose:
                stdout.write("    testing field: '%s'\n" % n)
                stdout.write('        shape...........')
            if arr2[n].shape != arr1[n].shape:
                nfail += 1
                if verbose:
                    stdout.write('shapes differ\n')
            else:
                if verbose:
                    stdout.write('OK\n')
                    stdout.write('        elements........')
                w,=numpy.where(arr1[n].ravel() != arr2[n].ravel())
                if w.size > 0:
                    nfail += 1
                    if verbose:
                        stdout.write('\n        '+\
                            "%s elements in field '%s' differ\n" % (w.size,n))
                else:
                    if verbose:
                        stdout.write('OK\n')


    if nfail == 0:
        if verbose:
            stdout.write('All tests passed\n')
        return True
    else:
        if verbose:
            stdout.write('%d differences found\n' % nfail)
        return False


def is_big_endian(array):
    """
    Return True if array is big endian.  Note strings are neither big
    or little endian.  The input must be a simple numpy array, not
    an array with fields.


    REVISION HISTORY:
        Created 2009, Erin Sheldon, NYU.
    """

    if numpy.little_endian:
        machine_big=False
    else:
        machine_big=True

    byteorder = array.dtype.base.byteorder
    return (byteorder == '>') or (machine_big and byteorder == '=')

def is_little_endian(array):
    """
    Return True if array is little endian. Note strings are neither big
    or little endian.  The input must be a simple numpy array, not
    an array with fields.

    REVISION HISTORY:
        Created 2009, Erin Sheldon, NYU.
    """

    if numpy.little_endian:
        machine_little=True
    else:
        machine_little=False

    byteorder = array.dtype.base.byteorder
    return (byteorder == '<') or (machine_little and byteorder == '=')


def to_native(array, inplace=False, keep_dtype=False):
    """
    NAME:
        to_native

    CALLING SEQUENCE:
        res=to_native(array, inplace=False, keep_dtype=False)

    PURPOSE:
        Convert an array to native byte order, updating the dtype to
        reflect this.  The array can have fields.  
    
    KEYWORDS:
        inplace:  Default False.  If True the data are byteswapped 
            in place and a reference to the original array is returned.  
            If False a copy is always retured, even if no data were
            swapped.
        keep_dtype: Default False.  Setting to True prevents the dtype from
            being updated to reflect the new byte order.

    REVISION HISTORY:
        Created 2009, Erin Sheldon, NYU.
    """


    if numpy.little_endian:
        machine_little=True
    else:
        machine_little=False

    data_little=False
    if array.dtype.names is None:
        data_little = is_little_endian(array)
    else:
        # assume all are same byte order: we only need to find one with
        # little endian
        for fname in array.dtype.names:
            if is_little_endian(array[fname]):
                data_little=True
                break

    if ( (machine_little and not data_little) 
            or (not machine_little and data_little) ):
        doswap=True
    else:
        doswap=False

    if doswap:
        outdata = byteswap(array, inplace, keep_dtype=keep_dtype)
    else:
        if inplace:
            outdata=array
        else:
            outdata=array.copy()

    return outdata




def to_big_endian(array, inplace=False, keep_dtype=False):
    """
    NAME:
        to_big_endian

    CALLING SEQUENCE:
        res=to_big_endian(array, inplace=False, keep_dtype=False)

    PURPOSE:
        Convert an array to big endian byte order, updating the dtype to
        reflect this.  The array can have fields.  
    
    KEYWORDS:
        inplace:  Default False.  If True the data are byteswapped 
            in place and a reference to the original array is returned.  
            If False a copy is always retured, even if no data were
            swapped.
        keep_dtype: Default False.  Setting to True prevents the dtype from
            being updated to reflect the new byte order.

    REVISION HISTORY:
        Created 2009, Erin Sheldon, NYU.
    """

    doswap=False
    if array.dtype.names is None:
        if not is_big_endian(array):
            doswap=True
    else:
        # assume all are same byte order: we only need to find one with
        # little endian
        for fname in array.dtype.names:
            if not is_big_endian(array[fname]):
                doswap=True
                break

    if doswap:
        outdata = byteswap(array, inplace, keep_dtype=keep_dtype)
    else:
        if inplace:
            outdata=array
        else:
            outdata=array.copy()

    return outdata

def to_little_endian(array, inplace=False, keep_dtype=False):
    """
    NAME:
        to_little_endian

    CALLING SEQUENCE:
        res=to_little_endian(array, inplace=False, keep_dtype=False)

    PURPOSE:
        Convert an array to big endian byte order, updating the dtype to
        reflect this.  The array can have fields. 
    
    KEYWORDS:
        inplace:  Default False.  If True the data are byteswapped 
            in place and a reference to the original array is returned.  
            If False a copy is always retured, even if no data were
            swapped.
        keep_dtype: Default False.  Setting to True prevents the dtype from
            being updated to reflect the new byte order.

    REVISION HISTORY:
        Created 2009, Erin Sheldon, NYU.
    """

    doswap=False
    if array.dtype.names is None:
        if not is_little_endian(array):
            doswap=True
    else:
        # assume all are same byte order: we only need to find one with
        # little endian
        for fname in array.dtype.names:
            if not is_little_endian(array[fname]):
                doswap=True
                break

    if doswap:
        outdata = byteswap(array, inplace, keep_dtype=keep_dtype)
    else:
        if inplace:
            outdata=array
        else:
            outdata=array.copy()


    return outdata



def byteswap(array, inplace=False, keep_dtype=False):
    """
    NAME:
        byteswap

    CALLING SEQUENCE:
        res=byteswap(array, inplace=False, keep_dtype=False)

    PURPOSE:
        Chance the byte order of an array, updating the dtype to reflect this.
        The array can have fields.   This is a wrapper for the .byteswap()
        method which does not update the dtype to reflect the new byte
        ordering.

    KEYWORDS:
        inplace:  Default False.  If True the data are byteswapped 
            in place and a reference to the original array is returned.  
            If False a copy is always retured, even if no data were
            swapped.
        keep_dtype: Default False.  Setting to True prevents the dtype from
            being updated to reflect the new byte order.

    REVISION HISTORY:
        Created 2009, Erin Sheldon, NYU.
    """

    outdata = array.byteswap(inplace)
    if not keep_dtype:
        outdata.dtype = outdata.dtype.newbyteorder()

    return outdata
      
def unique(arr, values=False):
    """
    NAME:
        unique
    
    CALLING SEQUENCE:
        un = unique(arr, values=False)

    PURPOSE:
        Return indices of unique elements of a numpy array, or optionally
        the unique values.  This is not order preserving. This is currently
        implemented in a slow fashion, should be updated.

    KEYWORDS:
        values:  Default False.  If True, return the unique values as
            opposed to just the indices which is the default.

    REVISION HISTORY:
        Created 2009, Erin Sheldon, NYU.
    """
    n = arr.size
    keep = numpy.zeros(n, dtype='i8')

    s = arr.argsort()

    val = arr[0]
    i=1
    nkeep = 0
    while i < n:
        ind = s[i]
        if arr[ind] != val:
            val = arr[ind]
            nkeep += 1
            keep[nkeep] = ind
        i += 1

    keep = keep[0:nkeep+1]
    if values:
        return arr[keep]
    else:
        return keep




def match(arr1input, arr2input):
    """
    NAME:
        match

    CALLING SEQUENCE:
        ind1,ind2 = match(arr1, arr2)

    PURPOSE:
        match two numpy arrays.  Return the indices of the matches or [-1] if
        no matches are found.  This means arr1[ind1] == arr2[ind2] is true for
        all corresponding pairs. Arrays must contain only unique elements

    METHOD:
        This is the "sort" method as borrowed from the Goddard idl astronomy
        library routine match.pro
    TODO:
        Implement the histogram method, which is faster but uses more
        memory.

    REVISION HISTORY:
        Created 2009, Erin Sheldon, NYU.
    """

    arr1 = numpy.array(arr1input, ndmin=1, copy=False)
    arr2 = numpy.array(arr2input, ndmin=1, copy=False)

    dtype = 'i8'
    n1 = len(arr1)
    n2 = len(arr2)

    if (n1 == 1) or (n2 == 1):
        # one of the arrays is length one
        if n2 > 1:
            sub2, = numpy.where(arr2 == arr1[0])
            if sub2.size > 0:
                sub1 = numpy.array([0], dtype=dtype)
            else:
                sub1 = numpy.array([-1], dtype=dtype)
        else:
            sub1, = numpy.where(arr1 == arr2[0])
            if sub1.size > 0:
                sub2 = numpy.array([0], dtype=dtype)
            else:
                sub2 = numpy.array([-1], dtype=dtype)

        return sub1, sub2


    # make a combined set
    tmp = numpy.zeros(n1+n2, dtype=arr1.dtype)
    tmp[0:n1] = arr1[:]
    tmp[n1:] = arr2[:]

    ind = numpy.zeros(n1+n2, dtype=dtype)
    ind[0:n1] = numpy.arange(n1)
    ind[n1:] = numpy.arange(n2)

    vec = numpy.zeros(n1+n2, dtype='b1')
    vec[n1:] = 1

    # sort combined list
    sortind = tmp.argsort()
    tmp = tmp[sortind]
    ind = ind[sortind]
    vec = vec[sortind]

    # this finds adjacent dups but only if they are not from the
    # same array.  Since we demand unique arrays I'm not sure why
    # the second check is needed
    firstdup, = numpy.where((tmp == numpy.roll(tmp,-1)) &
                            (vec != numpy.roll(vec,-1)) )
    if firstdup.size == 0:
        sub1 = numpy.array([-1], dtype=dtype)
        sub2 = numpy.array([-1], dtype=dtype)
        return sub1, sub2

    # both duplicate values...?
    dup = numpy.zeros(firstdup.size*2, dtype=dtype)

    even = numpy.arange( firstdup.size, dtype=dtype)*2
    dup[even] = firstdup
    dup[even+1] = firstdup+1

    # indices of duplicates
    ind = ind[dup]
    # vector id of duplicates
    vec = vec[dup]

    # now subscripts
    sub1 = ind[ numpy.where( vec == 0 ) ]
    sub2 = ind[ numpy.where( vec != 0 ) ]
    return sub1, sub2


def dict2array(d, sort=False, keys=None):
    """
    NAME:
      dict2array()

    CALLING SEQUENCE:
      arr = dict2array(dict, sort=False, keys=None)

    PURPOSE:
      Convert a dictionary to an array with fields (recarray, structured
      array).  This works for simple types e.g.  strings, integers, floating
      points.

    KEYWORDS:
        keys: provide a sequence of keys to copy.  This can be used to order
            the fields (standard dictionary keys are unordered) or copy only a
            subset of keys. 
        sort: Sort the keys.  

    COMMENTS:
        In python >= 3.1 dictionaries can be ordered.

    REVISION HISTORY:
        late 2009 created.  Erin Sheldon, BNL

    """
    desc=[]

    if keys is None:
        if sort:
            keys=sorted(d)
        else:
            keys=list(d.keys())

    for key in keys:
        # check key existence in case a set of keys was sent
        if key not in d:
            raise KeyError("Requested key %s not in dictionary" % key)

        if not isinstance(d[key], (int,long,float,str,unicode)):
            try:
                strval = '%s' % d[key]
                val = eval(strval)
            except:
                val = str(d[key])
        else:
            val = d[key]

        if isinstance(val, (int,long)):
            dt=long
        elif isinstance(val, float):
            dt=float
        elif isinstance(val, (str,unicode)):
            dt='S%s' % len(val)
        else:
            raise ValueError("Only support int, float, string currently, "
                             "found %s" % type(d[key]))

        desc.append( (key, dt) )

    a=numpy.zeros(1, dtype=desc)

    for key in keys:
        a[key] = d[key]

    return a


def splitarray(nper, var_input):
    """
    Name:
        splitarray()

    Purpose:
        Split up an array into chunks of at least a given size.  Return a
        list of these subarrays.  The ordering is perserved.

    Calling Sequence:
        split_list = splitarray(nper, array)
    
    Inputs:
        nper: Number obj elements in each sub-array.  Note, the last one
            may have fewer if len(array) % nper != 0
        array: A numpy array or object that can be converted to an array.

    Output:
        A list with all the sub-arrays.

    Example:
        In [1]: l=numpy.arange(25)
        In [2]: nper = 3
        In [3]: split_list = eu.numpy_util.splitarray(nper, l)
        In [4]: split_list
        Out[4]:
        [array([0, 1, 2]),
         array([3, 4, 5]),
         array([6, 7, 8]),
         array([ 9, 10, 11]),
         array([14, 12, 13]),
         array([15, 16, 17]),
         array([18, 19, 20]),
         array([23, 21, 22]),
         array([24])]


    Revision History:
        Created: 2010-04-05, Erin Sheldon, BNL 

    """


    var = numpy.array(var_input, ndmin=0, copy=False)

    ind = numpy.arange(var.size)

    # this will tell us which bin the object belongs to
    bin_nums = ind/nper

    h,rev = stat.histogram(bin_nums, binsize=1, min=0, rev=True)

    split_list = []
    for i in range(len(h)):
        if rev[i] != rev[i+1]:
            w=rev[ rev[i]:rev[i+1] ]

            split_list.append(var[w])

    return split_list

def randind(nmax, nrand):
    """
    Name:
        randind
    Calling Sequence:
        ind = randind(nmax, nrand)
    Purpose:
        Return nrand random indices, with replacement, in the open 
        range [0,nmax)
    """
    
    if nmax > (2**32-1):
        dtype = 'u8'
    else:
        dtype = 'u4'

    ind=numpy.zeros(nrand,dtype=dtype)

    rnd = numpy.random.random(nrand)
    ind[:] = arrscl( rnd, 0, nmax-1, arrmin=0.0, arrmax=1.0 )

    return ind
