# vim: set filetype=python :
import sys
from sys import stdout,stderr
import os
import pprint
import copy

try:
    import numpy
    # importing array will allow array types in the header to be properly
    # eval()uated.  Not sure if this works for all dtypes.
    from numpy import array
    have_numpy=True
except:
    have_numpy=False

try:
    try:
        # look for local install of recfile first
        from esutil import recfile
        have_recfile=True
    except:
        # might be installed elsewhere
        import recfile
        have_recfile=True
except:
    # ascii reading/writing not supported
    have_recfile=False


def Open(fobj, mode='r', delim=None, verbose=False, memmap=False):
    sf = SFile(fobj, mode=mode, delim=delim, verbose=verbose)
    if memmap and delim is None:
        return sf.get_memmap()
    else:
        return sf


class SFile():
    def __init__(self, fobj=None, mode='r', delim=None, 
                 padnull=False, ignorenull=False, verbose=False):
        """
        do some docs
        """
        self.open(fobj, mode=mode, delim=delim, verbose=verbose)

    def open(self, fobj, mode='r', delim=None, 
             verbose=False,
             padnull=False, ignorenull=False):
        """
        Open the file.  If the file already exists and the mode is 'r*' then
        a read of the header is attempted.  If this succeeds, delim is gotten
        from the header and the delim= keyword is ignored.
        """

        if not have_numpy:
            raise ImportError("numpy could not be imported")

        self.verbose=verbose

        self.close()
        self.padnull=padnull
        self.ignorenull=ignorenull

        if fobj is None:
            return

        if isstring(fobj):
            # expand shortcut variables
            fpath = os.path.expanduser(fobj)
            fpath = os.path.expandvars(fpath)

            if self.verbose:
                stdout.write("\nOpening file: %s\n" % fpath)

            if mode == 'r+' and not os.path.exists(fobj):
                # path doesn't exist but we want to append.  Change the
                # mode to write
                if self.verbose:
                    stdout.write("Requested append on non-existent file: "
                                 "Will create a new file\n")
                mode = 'w'

            self.fobj = open(fobj, mode)
        elif isinstance(fobj, file):
            self.fobj = fobj
        else:
            raise ValueError("Only support filenames and file objects "
                             "as input")

        if self.fobj.mode[0] == 'r':
            # For 'r' and 'r+' try to read the header
            if self.verbose:
                stdout.write("\tReading header\n")
            self.hdr = self.read_header()
            
            self.data_start = self.fobj.tell()

            self.delim = _match_key(self.hdr, '_delim')
            self.size = _match_key(self.hdr, '_size', require=True)
            self.descr = _match_key(self.hdr, '_dtype', require=True)
            self.dtype = numpy.dtype(self.descr)
            self.has_fields = (self.dtype.names is not None)
            # will be None unless no fields
            self.shape = self.get_shape()
        else:
            # get delim from the keyword.  This will be used for writing
            # later
            self.delim=delim


    def close(self):
        """
        Close any open file object.  Make sure fobj, _hdr, and delim are None
        """
        self.hdr=None
        self.data_start=None
        self.delim=None
        self.size=0
        self.descr=None
        self.dtype=None
        self.has_fields=None
        self.shape=None
        if hasattr(self, 'fobj'):
            if self.fobj is not None:
                if isinstance(self.fobj, file):
                    self.fobj.close()
        self.fobj=None

        self.padnull=False
        self.ignorenull=False

    def __repr__(self):
        s = []

        if isinstance(self.fobj,file):
            s += ["filename: '%s'" % self.fobj.name]
        if self.delim is not None:
            s=["delim: '%s'" % self.delim]

        s += ["size: %s" % self.size]

        if self.shape is not None:
            s += ["shape: " + pprint.pformat(self.shape)]
        #if self.has_fields is not None:
            #s += ["has_fields: %s" % self.has_fields]
        if self.descr is not None:
            s += ["dtype: \n"+pprint.pformat(self.descr)]

        if self.hdr is not None:
            hs = self.h2string()
            if hs != '':
                s += ["hdr: \n"+hs]
        # maybe we can show an example row
        old="""
        if isinstance(self.fobj,file) and self.has_fields:
            try:
                tmp = self.read(rows=0)
                s += ["first row: "+pprint.pformat(tmp)]
            except:
                pass
        """
        s = "\n".join(s)
        return s

    def h2string(self, strip=True):
        if self.hdr is None:
            return ''
        newd = {}

        skipkeys=['_DTYPE','_SIZE','_NROWS','_HAS_FIELDS','_DELIM','_SHAPE']
        for key in self.hdr:
            if strip:
                if key not in skipkeys:
                    newd[key] = self.hdr[key]
            else:
                news[key] = self.hdr[key]

        if len(newd) == 0:
            return ''
        return pprint.pformat(newd)



    def write(self, data, header=None):
        """
        do some docs
        """

        # Write or update the header. If we are updating the file, this will
        # just alter the number of rows marked in the header and in self.size.
        # Either way, self.fobj will point to the end of the file, ready to
        # write the data

        self._write_header(data, header=header)

        if not self.has_fields:
            self._write_simple(data)
        else:
            self._write_structured(data)

    def _write_structured(self, data):
        if self.verbose:
            stdout.write("Writing %s: %s\n" % \
                            (data.size,pprint.pformat(data.dtype.descr)))
        if (self.delim is not None) and (have_recfile is not True):
            stdout.write("delim='"+self.delim+"'\n")
            stdout.write("have_recfile=%s\n" % have_recfile)
            raise ValueError("recfile module not found writing ascii "
                             "records")
        elif (self.delim is not None):
            # let recfile deal with ascii writing
            r = recfile.Open(self.fobj, mode='u', delim=self.delim, 
                             dtype=data.dtype)
            # simple view of data
            dataview = data.view(numpy.ndarray) 
            r.Write(dataview, 
                    padnull=self.padnull, ignorenull=self.ignorenull)
        else:
            # Write data out as a binary chunk
            data.tofile(self.fobj)

    def _write_simple(self, data):
        if self.verbose:
            stdout.write("Writing %s: '%s'\n" % (data.size,data.dtype.str))
        # got to wrap this because tofile does not support delim=None
        if self.delim is not None:
            data.tofile(self.fobj, sep=self.delim)
        else:
            data.tofile(self.fobj)

    def get_subset(self, rows=None, fields=None, columns=None):
        return SFileSubset(self, rows=rows, fields=fields, columns=columns)

    def get_memmap(self, mode='r', view=None, header=False):

        if self.delim is not None:
            raise ValueError("Cannot memory map ascii files")

        if self.fobj.tell() != self.data_start:
            self.fobj.seek(self.data_start)


        if not self.has_fields and self.shape is not None:
            shape = self.shape
        else:
            shape = (self.size,)

        result = numpy.memmap(self.fobj, dtype=self.dtype, shape=shape, 
                              mode=mode, offset=self.fobj.tell())
        if view is not None:
            result = result.view(view)
        if header:
            return result, self.hdr
        else:
            return result



    def read(self, rows=None, fields=None, columns=None, header=False, 
             view=None, split=False):
        """
        Read the data into memory.
        """
        
        if self.fobj.tell() != self.data_start:
            self.fobj.seek(self.data_start)

        if not self.has_fields:
            result = self._read_simple()
        else:
            result = self._read_structured(rows=rows, 
                                           fields=fields, columns=columns)
        if view is not None:
            result = result.view(view)
        elif split:
            result = split_fields(result)

        if header:
            return result, self.hdr
        else:
            return result

    def __getitem__(self, arg):
        """
        sf = SFile(....)

        # read subsets of columns and/or rows from the file.  Note, lists
        # of columns or rows cannot be tuples, due to how the __getitem__
        # call works.

        # read subsets of columns
        data = sf['fieldname']
        data = sf[ ['field1','field2',...] ]    # can also be an array

        # read subsets of rows
        data = sf[ 35 ]
        data = sf[ 35:88 ]
        data = sf[ [3,234,5551,.. ] ]           # can also be an array

        # read subset of rows *and* columns.
        data = sf['fieldname', 3:58]
        data = sf[rowlist, fieldlist]
        data = sf[fieldlist,rowlist]

        If a single argument is entered, that is set to arg.
        If more than one is entered, arg is set to a tuple.  d'oh!,  Hard
            to parse
        """
        if not self.has_fields:
            raise RuntimeError("For simple arrays, use a memmap object "
                               "returned by get_memmap()")
        if not isinstance(arg,tuple):
            send_arg = (arg,)
        else:
            send_arg = arg

        rows, columns = self.process_args_as_rows_and_columns(send_arg)
        return self.read(rows=rows, columns=columns)

    def slice2rows(self, start, stop, step=None):
        if start is None:
            start=0
        if stop is None:
            stop=self.size
        if step is None:
            step=1

        tstart = _fix_range(start, self.size)
        tstop  = _fix_range(stop,  self.size)
        if tstart == 0 and tstop == self.size:
            # this is faster: if all fields are also requested, then a 
            # single fread will be done
            return None
        if stop < start:
            raise ValueError("start is greater than stop in slice")
        return numpy.arange(tstart, tstop, step, dtype='i8')

    def process_args_as_rows_and_columns(self, args):
        """

        args must be a tuple.  Only the first one or two args are used.

        We must be able to interpret the args as as either a column name or
        row number, or sequences thereof.  Numpy arrays and slices are also
        fine.

        Examples:

            Single arguments:
                ( 'field1', )
                ( 54, )
                ( ('f1','f2'), )
                ( [3,4,5,6], )
            Two arguments:
                ( 'field36', 27 )
                ( [33,44], ['ra','dec','flux'] )
                ( 'ra', slice(5,10) )

        Returns rows,columns but one will be None.  If both entries can be
        interpreted as rows, the last is used.  Similarly for fields.

        """

        columns=None
        rows=None

        for arg in args[0:2]:

            if isinstance(arg, (tuple,list,numpy.ndarray)):
                # a sequence was entered
                if isstring(arg[0]):
                    columns = arg
                else:
                    rows = arg
            elif isstring(arg):
                # a single string was entered
                columns = arg
            elif isinstance(arg, slice):
                rows = self.slice2rows(arg.start, arg.stop, arg.step)
            else:
                # a single object was entered.  Probably should apply some more 
                # checking on this
                rows=arg

        return rows, columns




    def get_shape(self):
        if self.has_fields:
            return None
        shape = _match_key(self.hdr, '_shape')
        if shape is None:
            return None
        ashape = numpy.array(shape,ndmin=1)
        if ashape.prod() == self.size:
            return shape
        else:
            return None

    def _read_structured(self, rows=None, fields=None, columns=None):
        if self.verbose:
            stdout.write("\tReading as a structured array\n")


        rows2read = self._get_rows2read(rows)
        fields2read = self._get_fields2read(fields, columns=columns)

        if fields2read is None and rows2read is None and self.delim is None:
            # Its binary and all, just use fromfile
            result = numpy.fromfile(self.fobj,dtype=self.dtype)
        else:
            if have_recfile:
                result = self._recfile_read(rows=rows2read, fields=fields2read)
            else:
                result = self._memmap_read(rows=rows2read, fields=fields2read)

        return result

    def _recfile_read(self, rows=None, fields=None):
        delim=self.delim
        if delim is None:
            delim=""
        robj = recfile.Open(self.fobj, nrows=self.size, mode='r', 
                            dtype=self.dtype, delim=delim)
        return robj.Read(rows=rows, fields=fields)

    def _memmap_read(self,rows=None, fields=None):
        raise RuntimeError("Not Yet Implemented")

    def _read_simple(self):
        if self.verbose:
            stdout.write("\tReading as a simple array\n")
        # delim can't be None, so case it
        if self.delim is None:
            result = numpy.fromfile(self.fobj, dtype=self.dtype, 
                                    count=self.size)
        else:
            result = numpy.fromfile(self.fobj, dtype=self.dtype, 
                                    count=self.size, sep=self.delim)
        return self._try_reshape(result) 

    def _try_reshape(self, data):
        shape = _match_key(self.hdr, '_shape')
        if shape is None:
            return data

        # Only use it if the lengths match
        try:
            ashape = numpy.array(shape, ndmin=1)
        except:
            return data
        if ashape.prod() == data.size:
            if self.verbose:
                stdout.write("\tReshaping array to "
                             "%s\n" % pprint.pformat(shape))
            return data.reshape(shape)
        else:
            if self.verbose:
                stdout.write("_shape number of elements does not match "
                             "array size: not reshaping\n")
            return data

    def _get_rows2read(self, rows):
        if rows is None:
            return None
        rows2read = numpy.array(rows,ndmin=1,copy=False)
        if rows2read is not None and self.verbose:
            stdout.write("\t\tReading %s rows\n" % len(rows2read))

        return rows2read

    def _get_fields2read(self, fields, columns=None):
        if fields is None:
            fields=columns

        if fields is None:
            return None
        elif isinstance(fields, (list,numpy.ndarray)):
            f=fields
        elif isinstance(fields,tuple):
            f=list(fields)
        elif isstring(fields):
            f=[fields]
        else:
            raise ValueError('fields must be list,tuple,string or array')

        if not isstring(f[0]):
            # this is probably a list of column numbers, convert to strings
            allnames = self.dtype.names
            f = [allnames[i] for i in f]

        if self.verbose:
            _out = (len(f), pprint.pformat(f))
            stdout.write("\t\tReading %s fields: %s\n" % _out)

        return f





    def _make_header(self, data, header=None):
            if header is None:
                head={}
            else:
                head=copy.deepcopy(header)

            for key in ['_size','_nrows','_delim','_shape','_has_fields']:
                if key in head: del head[key]
                if key.upper() in head: del head[key.upper()]

            has_fields = (data.dtype.names is not None)
            if has_fields:
                descr = data.dtype.descr
            else:
                descr = str(data.dtype.str)
                head['_SHAPE'] = data.shape

            head['_HAS_FIELDS'] = has_fields

            if self.delim is not None:
                head['_DELIM'] = self.delim

                # Text file. Remove the byte order specification. 
                descr = self._remove_byteorder(descr)

            head['_DTYPE'] = descr

            return head

    def _write_header(self, data, header=None):

        if self.hdr is not None:
            # we are appending data.  Make sure we are dealing with a
            # structured array, or else we will abort the append.

            # Just update the nrows and move to the end
            self._update_size(data.size)
            if self.verbose:
                stdout.write("\tSeeking to end of file\n")
            self.fobj.seek(0,2) # Seek to end of file
        else:

            if self.verbose:
                stdout.write("\tCreating new header\n")
            self.hdr = self._make_header(data, header=header)

            self.fobj.seek(0)

            self._write_size(data.size)
            self.size = data.size

            # As long as the dict contains types that can be represented as
            # constants, this pretty printing can be eval()d.

            pprint.pprint(self.hdr, stream=self.fobj)

            self.fobj.write('END\n')
            self.fobj.write('\n')

    def _remove_byteorder(self, descr):
        if isstring(descr):
            return descr[1:]

        new_descr = []
        for d in descr:
            # d is a tuple, make it a list
            newd = list( copy.copy(d) )

            tdef = newd[1]
            tdef = tdef[1:]
            newd[1] = tdef
            newd = tuple(newd)
            new_descr.append(newd)

        return new_descr

    def _update_size(self, size_add):
        size_current = self.size
        if size_current is None:
            raise RuntimeError('Attempting to update size but not found in header')
        size_new = size_current + size_add

        if self.verbose:
            stdout.write("\tUpdating size to %s\n" % size_new)

        self._write_size(size_new)
        self.size = size_new
        self.hdr['_SIZE'] = size_new

    def _write_size(self, size):
        # Go to the beginning of the file
        self.fobj.seek(0)
        # Specially formatted fixed-length for updating later
        out = 'SIZE = %20d\n' % (size,)
        self.fobj.write(out)


    def _extract_size(self, header):
        if not isinstance(header,dict):
            raise RuntimeError('header must be a dict')

        size = _match_key(header,'_size')
        if size is None:
            size = _match_key(header,'_nrows')
            if size is None:
                raise RuntimeError("Header must contain the size in first "
                                   "row as 'SIZE = %20d'")
        return long(size)


    def read_header(self):
        """
        sfile..read_header()

        Read the header from a simple self-describing file format with an 
        ascii header.  See the write() function for information
        about reading this file format, and read() for reading.

        Calling Sequence:
            sfile.read_header(infile)

        Inputs:
            infile: A string or file pointer for the input file.

        Examples:
            import sfile
            hdr=sfile.read_header('test.rec')


        The file format:
          First line:
              SIZE = --------------number

        where if possible the number should be formatted as %20d.  This is
        large enough to hold a 64-bit number.  This exact formatting is
        required so SIZE can be updated *in place* when appending rows to a
        file holding structured arrays.  Note the file can be read as long as
        the first line reads SIZE = some_number but appending requires the
        exact format.


        Last two lines of the header region must be:
                END
                blank line
        case does not matter.

          
        In between the SIZE and END lines is the header data.  This is a string
        that must eval() to a dictionary.  It must contain the following entry:

              _DTYPE = array data type description in list of tuples or
                string form (case does not matter).
                  
                for a structured array.
                    [('field1', 'f8'), ('f2','2i4')]
                for a simple array:
                    '<f4'

        As noted above, only files holding structured arrays can be appended.

        If the file holds a simple array, and the dtype field is a simple
        string, then the following keyword can be used to reshape the array:

              '_SHAPE'

        If the total elements in the _shape field matches the size then it will
        be used to reshape the array before returning or when using memory
        maps.

        If the data are ascii then delimiter must be given in the keyword

              _DELIM.  
              
        This can be for example ',', ' ', or a tab character.  Again, case does
        not matter.  

        The rest of the keywords are open and any variable can be used as long
        as it can be eval()d.

        An example header:
            SIZE =                   10
            {'_DELIM': ',',
             '_DTYPE': [('x', 'f4'),
                        ('y', 'f4'),
                        ('ra', 'f8'),
                        ('dec', 'f8'),
                        ('exposurename', 'S20'),
                        ('ccd', 'i1'),
                        ('size_flags', 'i4'),
                        ('magi', 'f4'),
                        ('sigma0', 'f4'),
                        ('star_flag', 'i4'),
                        ('shear_flags', 'i4'),
                        ('shapelet_sigma', 'f4'),
                        ('shear1', 'f4'),
                        ('shear2', 'f4'),
                        ('shear_cov00', 'f4'),
                        ('shear_cov01', 'f4'),
                        ('shear_cov11', 'f4')],
             'listvar': [1, 2, 3],
             'subd': {'subd1': 'subfield', 'sublist': [8.5, 6.6]},
             'svar': 'hello',
             'test1': 35}
            END

            -- data begins --

        Modification History:
            Created: 2007-05-25, Erin Sheldon, NYU
            Allow continuation characters "\\" to continue header keywords
                onto the next line.  2009-05-05

            Switched header to be simply a dictionary representation.
                SIZE = %20d
                { a dictionary representation }
                END
                blank line
            This is much more powerful and simple.  Anything that can be eval()d
            can be in the header, including numpy arrays.  
                        2009-10-28. Erin Sheldon, BNL

            Allow simple arrays (without fields) to be written.  Switch to
            using SIZE = %20d on the first row instead of NROWS, this makes
            more sense for both structured and simple arrays.  Note the
            old style can still be read, just not appended.
                2009-11-16, ESS
            
        """

        if not have_numpy:
            raise ImportError("numpy could not be imported")

        self.fobj.seek(0)
        line = self.fobj.readline().strip()
        lsplit = line.split('=')
        if len(lsplit) != 2:
            raise ValueError("First line of header must be SIZE = %20d")
        fname=lsplit[0].strip()
        if fname.upper() != 'SIZE' and fname.upper() != 'NROWS':
            raise ValueError("First line of header must be SIZE = %20d")

        if fname.upper() == 'NROWS':
            self.cannot_append_oldheader=True
        else:
            self.cannot_append_oldheader=False

        size = eval(lsplit[1])


        # Read through the header until we hit "END"
        lines = []
        line=self.fobj.readline().strip()
        while line.upper() != 'END':
            lines.append(line)
            line=self.fobj.readline().strip()

        # read one more line, which should be blank
        line = self.fobj.readline()
        if line.strip() != '':
            raise RuntimeError("Header should end with END on it's own line "
                               "followed by a blank line")

        hdrstring = ' '.join(lines)
        hdr = eval(hdrstring)

        hdr['_SIZE'] = size

        return hdr

    def header(self):
        return self.hdr



class SFileSubset():
    def __init__(self, sf, fields=None, columns=None, rows=None):
        """
        Input is the SFile instance and a list of column names.
        """

        if columns is None:
            columns=fields

        self.sfile = sf
        self.columns = columns
        self.rows=rows

        self._match_columns()
        self._match_rows()

    def __getitem__(self, *args):
        rows, columns = process_args_as_rows_and_columns(args)
        if rows is not None:
            self.rows=rows
        if columns is not None:
            self.columns=columns
        return SFileSubset(self.sfile, rows=self.rows, columns=self.columns)

    def __getslice__(self, i, j):
        i=_fix_range(i, self.sfile.size)
        j=_fix_range(j, self.sfile.size)
        if j < i:
            self.rows=None
        else:
            self.rows=numpy.arange(i,j, dtype='i8')
        return SFileSubset(self.sfile, rows=self.rows, columns=self.columns)



    def read(self, view=None, split=False):
        """
        Read the data from disk and return as a numpy array
        """

        return self.sfile.read(rows=self.rows, columns=self.columns, 
                               view=view, split=split)

    def _match_columns(self):
        if self.columns is None:
            return
        if isstring(self.columns):
            self.columns = [self.columns]

        # we don't support tuples in recfile...
        if isinstance(self.columns, tuple):
            self.columns = list(self.columns)
        for col in self.columns:
            if col not in self.sfile.dtype.names:
                raise ValueError("column not found: '%s'" % col)

    def _match_rows(self):
        if self.rows is None:
            return
        # we don't support tuples in recfile...
        self.rows = numpy.array(self.rows, copy=False, ndmin=1)
        maxrow=self.rows.max()
        minrow=self.rows.min()
        if self.rows.min() < 0:
            raise ValueError("min row: %s out of range" % minrow)
        if self.rows.max() >= self.sfile.size:
            raise ValueError("max row: %s out of range" % maxrow)

    def __repr__(self):
        s=[]
        if self.columns is not None:
            s += ["column subset: " + pprint.pformat(self.columns)]
        if self.rows is not None:
            s += ["row subset: " + pprint.pformat(self.rows)]
        if len(s) > 0:
            s += ['from:\n']
        s+=[self.sfile.__repr__()]
        s = "\n".join(s)
        return s

def process_args_as_rows_and_columns(args, maxrow=None):
    """
    args must be a tuple.  Only the first one or two args are used.

    We must be able to interpret the args as as either a column name or
    row number, or sequences thereof.  Numpy arrays and slices are also fine.
    Examples:

        Single arguments:
            ( 'field1', )
            ( 54, )
            ( ('f1','f2'), )
            ( [3,4,5,6], )
            ( ['x','y'], )
            ( (8,10), )
        Two arguments:
            ( 'field36', 27 )
            ( [33,44], ('ra','dec','flux') )
            ( 'ra', slice(5,10) )

    Returns rows,columns but one will be None.  If both entries can be
    interpreted as rows, the last is used.  Similarly for fields.

    """

    print args
    columns=None
    rows=None

    for arg in args[0:2]:

        if isinstance(arg, (tuple,list,numpy.ndarray)):
            # a sequence was entered
            if isstring(arg[0]):
                columns = arg
            else:
                rows = arg
        elif isstring(arg):
            # a single string was entered
            columns = arg
        elif isinstance(arg, slice):
            start = _fix_range(arg.start, self.size)
            stop = _fix_range(arg.stop, self.size)
            rows = numpy.arange(start, stop, dtype='i8')
        else:
            # a single object was entered.  Probably should apply some more 
            # checking on this
            rows=arg

    print 'rows=',rows
    print 'columns=',columns
    return rows, columns

def _fix_range(i, maxval):
    if i < 0:
        i=maxval-i
    if i > maxval:
        i=maxval
    return i



def write(array, outfile, header=None, delim=None, 
          padnull=False, ignorenull=False, append=False, verbose=False):
    """
    sfile.write()

    Write a numpy array into a simple self-describing file format with an 
    ascii header.  See the read() function for information
    about reading this file format.

    Calling Sequence:
        sfile.write(array, outfile, delim=None, padnull=False, append=False, header=)

    Inputs:
        array: A numpy array.
        outfile: A string or file pointer for the output file.

    Optional Inputs:
        header=: A dictionary containing keyword-value pairs to be added to
            the header.

        delim=None: Delimiter between fields.  Default is None for binary.  For
            ascii can be any string, e.g. ',', ' ', or a tab character.

        padnull=False:  
            When writing ascii, replace Null characters with spaces.  This is
            useful when writing files to be read in by programs that do not
            recognize null characters, e.g. sqlite databases.  But note, if
            read back in these fields will not compare equal with the original
            data!

        ignorenull=False:  
            When writing ascii, ignore Null characters.  This is useful when
            writing files to be read in by programs that do not recognize null
            characters, e.g. sqlite databases.  But note you will not be
            able to read the data back in with sfile.read() becuase the fields
            are no longer the correct length!

        append=False: Append to the file. Default is False. If set to True,
            then what happens is situation dependent:
                1) if the input is a file object then it is assumed there is 
                    an existing header.  The header is updated to reflect the
                    new appended rows after writing.
                2) if the input is a string and the file exists, then the file
                    is opened with mode "r+", it is assumed the header
                    exists, and the header is updated to reflext the new
                    appended rows after writing.
                3) if the input is a string and the file does *not* exist,
                    then the file is opened with mode "w" and the request
                    to append is ignored.

    Examples:
        import sfile
        hdr={'date': '2007-05-12','age': 33} 
        sfile.write(arr, 'test.rec', header=hdr)

        sfile.write(arr2, 'test.rec', append=True)

    File Format:
        The file format is an ascii header followed by data in binary or rows
        of ascii.  The data columns must be fixed length in order to map onto
        numpy arrays.  See the documentation for read_header() for details
        about the header format.

    Modification History:
        Created: 2007-05-25, Erin Sheldon, NYU
        Ignore append=True when file does not yet exist.
        Allow continuation characters "\\" to continue header keywords
        onto the next line.  2009-05-05

    """



    #def write(array, outfile, header=None, delim=None, 
    #      padnull=False, ignorenull=False, append=False):

    if append:
        mode = 'r+'
    else:
        mode = 'w'

    sf=SFile(outfile, mode=mode, delim=delim, 
             padnull=padnull, ignorenull=ignorenull, verbose=verbose)
    sf.write(array, header=header)

    return


    # old code

    if not have_numpy:
        raise ImportError("numpy could not be imported")

    # Get the file object.  If append is requested and it is found 
    # appropriate, doappend will be True, else False
    fobj, f_isstring, doappend = _GetFobj(outfile, 'write', append=append)

    # Write the header
    nrows = array.size
    descr = array.dtype.descr
    _write_header(fobj, nrows, descr, delim=delim, append=doappend, 
                  header=header)

    if (delim is not None) and (have_recfile is not True):
        stdout.write("delim='"+delim+"'\n")
        stdout.write("have_recfile=%s\n" % have_recfile)
        raise ValueError('recfile module not found for ascii writing')
    elif (delim is not None):
        # let recfile deal with delimiter writing
        r = recfile.Open(fobj, mode='u', delim=delim, dtype=array.dtype)
        #r.Write(array)
        r.Write(array.view(numpy.ndarray), 
                padnull=padnull, ignorenull=ignorenull)
    else:
        # Write data out as a binary chunk
        array.tofile(fobj)

    # Need to close if string was input
    if f_isstring:
        fobj.close()

def read(infile, rows=None, fields=None, columns=None, 
         header=False, view=None, memmap=False, verbose=False):
    """
    sfile.read()

    Read a numpy array from a simple self-describing file format with an ascii
    header.  See the write() function for information about this file format.
    For ascii files the recfile package is used for reading and writing.

    Calling Sequence:
        arr = sfile.read(infile, rows=None, columns=None, 
                         header=False, view=numpy.ndarray)

    Inputs:
        infile: A string or file pointer for the input file.
    Optional Inputs:
        rows=: A scalar, array, list or tuple of row numbers to read.  
            Default is all.
        columns=: A scalar, list or tuple of strings naming columns to read 
            from the file.  Default is all.
        fields=:  Same as sending columns=.
        header=False:  If True, return both the array and the header dict in
            a tuple.
        view=:  How to view the array.  Default is numpy.ndarray.

    Examples:
        import sfile
        arr=sfile.read('test.rec')

        arr2, hdr = sfile.read('test.rec', 
                               rows=[3,4], fields=['ra', 'dec'], header=True)

    File Format:
        The file format is an ascii header followed by data in binary or rows
        of ascii.  The data columns must be fixed length in order to map onto
        numpy arrays.  See the documentation for read_header() for details
        about the header format.


    Modification History:
        Created: 2007-05-25, Erin Sheldon, NYU
        Allow continuation characters "\\" to continue header keywords
        onto the next line.  2009-05-05

        Switched over to new header format.  2009-10-38, Erin Sheldon, BNL.
    """

    #def read(infile, rows=None, fields=None, columns=None, norecfile=False,
    #         header=False, view=None, memmap=False):

    sf = SFile(infile, verbose=verbose)
    if memmap:
        return sf.get_memmap(view=view, header=header)
    else:
        return sf.read(rows=rows, fields=fields, columns=columns, 
                       view=view, header=header)

    # old code


    if not have_numpy:
        raise ImportError("numpy could not be imported")

    if not have_recfile:
        norecfile=True

    # Get the file object
    fobj,f_isstring,junk = _GetFobj(infile,'read')

    # Get the header
    hdr=read_header(fobj)

    delim = _match_key(hdr,'_delim')

    if delim is not None:
        if not have_recfile:
            raise ValueError("Cannot read text files without the "
                             "recfile package\n")


    # read the header
    # number of rows
    nrows = _GetNrows(hdr)

    # The dtype
    dt = _GetDtype(hdr)
    
    if fields is None:
        # let columns be a synonym for fields
        if columns is not None:
            fields=columns

    rows2read, nr =_get_rows2read(rows)
    fields2read, nf =_get_fields2read(fields, dt)
    if (nf == 0) & (nr == 0) & (delim is None):
        # Its binary and all, just use fromfile
        result = numpy.fromfile(fobj,dtype=dt)
    else:
        if delim is None and (memmap or norecfile):
            mmap = numpy.memmap(fobj, dtype=dt, shape=(nrows,), 
                                mode='r', offset=fobj.tell())

            if (nf == 0) and (nr != 0):
                # all columns, but a subset of rows, is requested this is
                # about a factor of two slower than recfile on the big files I
                # tested, so I don't see the point of using memmap at all.
                result = numpy.empty(nr, dtype=dt)
                result[:] = mmap[ rows2read ]
            elif (nf != 0) and (nr == 0):
                
                # all rows but a subset of columns requested.  Because 
                # memmap must first read all the rows then extract columns
                # using memmap is basically a bad idea.

                new_dt = [tdt for tdt in dt if tdt[0] in fields2read]
                result = numpy.empty( nrows, dtype=new_dt )
                for name in fields2read:
                    result[name][:] = mmap[name][:]
            else:

                # a subset of both rows and columns is requested.  memmap
                # reads the rows first then extracts columns, so could be a
                # bad idea for big file

                new_dt = [tdt for tdt in dt if tdt[0] in fields2read]
                result = numpy.empty( nr, dtype=new_dt )
                for name in fields2read:
                    result[name][:] = mmap[name][rows2read]

        else:
            if (not norecfile) or (delim is not None):
                dtype=numpy.dtype(dt)
                if delim is None:
                    send_delim = ""
                else:
                    send_delim = delim
                robj = recfile.Open(fobj, nrows=nrows, mode='r', dtype=dtype,
                                    delim=send_delim)
                result = robj.Read(rows=rows2read, fields=fields2read)
            else:

                # The data are binary but we are to extract subsamples after
                # reading all the data.  This is either because we don't have
                # recfile or it was explicitly requested not to use recfile

                result = numpy.fromfile(fobj,dtype=dt)
                if rows2read is not None and len(rows2read) < nrows:
                    result = result[rows2read]
                if fields2read is not None and len(fields2read) < len(dt):
                    result = extract_fields(result, fields2read)




    # close file if was opened locally
    if f_isstring:
        fobj.close()

    if view is not None:
        result = result.view(view)

    if header:
        return result, hdr
    else:
        return result

def read_header(infile, verbose=False):
    """
    sfile.read_header()

    Read the header from a simple self-describing file format with an 
    ascii header.  See the write() function for information
    about reading this file format, and read() for reading.

    Calling Sequence:
        sfile.read_header(infile)

    Inputs:
        infile: A string or file pointer for the input file.

    Examples:
        import sfile
        hdr=sfile.read_header('test.rec')


    The file format:
      First line:
          NROWS = --------------number
      where the number is formatted as %20d.  This is large enough to hold
      a 64-bit number.  This exact formatting is required so NROWS can
      be updated *in place* when appending rows to the file.


      Last two lines of the header region must be:
          END
          blank line
      case does not matter.

      
      In between the NROWS and END lines is the header data.  This is a 
      string that must eval() to a dictionary.  It must
      contain the following entry:

          _DTYPE = array data type description in list of tuples form. For
              example [('field1', 'f8'), ('f2','2i4')]

      case does not matter.

      If the data are ascii then delimiter must be given in the keyword
          _DELIM.  This can be for example ',', ' ', or a tab character.
      Again, case does not matter.  

      The rest of the keywords are open and any variable can be used
      as long as it can be eval()d.

      An example header:
        NROWS =                   10
        {'_DELIM': ',',
         '_DTYPE': [('x', 'f4'),
                    ('y', 'f4'),
                    ('ra', 'f8'),
                    ('dec', 'f8'),
                    ('exposurename', 'S20'),
                    ('ccd', 'i1'),
                    ('size_flags', 'i4'),
                    ('magi', 'f4'),
                    ('sigma0', 'f4'),
                    ('star_flag', 'i4'),
                    ('shear_flags', 'i4'),
                    ('shapelet_sigma', 'f4'),
                    ('shear1', 'f4'),
                    ('shear2', 'f4'),
                    ('shear_cov00', 'f4'),
                    ('shear_cov01', 'f4'),
                    ('shear_cov11', 'f4')],
         'listvar': [1, 2, 3],
         'subd': {'subd1': 'subfield', 'sublist': [8.5, 6.6]},
         'svar': 'hello',
         'test1': 35}
        END

        -- data begins --

    Modification History:
        Created: 2007-05-25, Erin Sheldon, NYU
        Allow continuation characters "\\" to continue header keywords
            onto the next line.  2009-05-05

        Switched header to be simply a dictionary representation.
            NROWS = %20d
            { a dictionary representation }
            END
            blank line
        This is much more powerful and simple.  Anything that can be eval()d
        can be in the header, including numpy arrays.  
                    2009-10-28. Erin Sheldon, BNL
    """

    sf = SFile(infile, verbose=verbose)
    return sf.hdr


    # old code
    if not have_numpy:
        raise ImportError("numpy could not be imported")

    # Get the file object
    fobj,f_isstring,junk = _GetFobj(infile,'read')

    line = fobj.readline().strip()
    lsplit = line.split('=')
    if len(lsplit) != 2:
        raise ValueError("First line of header must be NROWS = %20d")
    fname=lsplit[0].strip()
    if fname.upper() != 'NROWS':
        raise ValueError("First line of header must be NROWS = %20d")

    nrows = eval(lsplit[1])


    # Read through the header until we hit "END"
    lines = []
    line=fobj.readline().strip()
    while line.upper() != 'END':
        lines.append(line)
        line=fobj.readline().strip()

    # read one more line, which should be blank
    line = fobj.readline()
    if line.strip() != '':
        raise RuntimeError("Header should end with END on it's own line "
                           "followed by a blank line")

    hdrstring = ' '.join(lines)
    hdr = eval(hdrstring)

    hdr['_NROWS'] = nrows

    # close file if was opened locally
    if f_isstring:
        fobj.close()

    return hdr




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

def _match_key(d, key, require=False):
    """
    Match the key in a case-insensitive way and return the value. Return None
    if not found or raise an error if require=True
    """
    if not isinstance(d,dict):
        raise RuntimeError('Input object must be a dict')
    keys = list( d.keys() )
    keyslow = [k.lower() for k in keys]
    keylow = key.lower()
    if keyslow.count(keylow) != 0:
        ind = keyslow.index(keylow)
        return d[keys[ind]]
    else:
        if not require:
            return None
        else:
            raise RuntimeError("Could not find required key: '%s'" % key)
 

_major_pyvers = int( sys.version_info[0] )
def isstring(obj):
    if _major_pyvers >= 3:
        string_types=(str, numpy.string_)
    else:
        string_types=(str, unicode, numpy.string_)

    if isinstance(obj, string_types):
        return True
    else:
        return False

def test():
    """
    very simple test
    """
    import tempfile
    tmpfile = tempfile.TemporaryFile(suffix='.sf')
    x=numpy.array([(1.0, 3),(4.5,2)], dtype=[('fcol','f4'),('icol','i4')])

    write(x, tmpfile)
    tmpfile.seek(0)
    read(tmpfile)

    tmpfile.close()








# old crap

def copy_fields(arr1, arr2):
    """
    Copy the fields that match
    """
    if arr1.size != arr2.size:
        raise ValueError('arr1 and arr2 must be the same size')

    names1=arr1.dtype.names
    names2=arr2.dtype.names
    for name in names1:
        if name in names2:
            arr2[name] = arr1[name]

def extract_fields(arr, keepnames):
    if type(keepnames) != list and type(keepnames) != numpy.ndarray:
        keepnames=[keepnames]
    arrnames = list( arr.dtype.names )
    new_descr = []
    for d in arr.dtype.descr:
        name=d[0]
        if name in keepnames:
            new_descr.append(d)
    if len(new_descr) == 0:
        raise ValueError('No field names matched')

    shape = arr.shape
    new_arr = numpy.zeros(shape,dtype=new_descr)
    copy_fields(arr, new_arr)
    return new_arr



def _write_header(fobj, nrows, descr, delim=None, header=None, append=False):
    import pprint

    if append:
        # Just update the nrows and move to the end
        _UpdateNrows(fobj, nrows)
        fobj.seek(0,2) # Seek to end of file
    else:
        # Write a full new header
        if header is None:
            head={}
        else:
            head=copy.deepcopy(header)

        if delim is not None:
            # Text file
            # In this case byte order in the dtype could cause errors
            descr = _remove_byteorder(descr)

        fobj.seek(0)

        _WriteNrows(fobj, nrows)

        head['_DTYPE'] = descr
        if delim is not None:
            head['_DELIM'] = delim
        else:
            # don't write delim unless it is required
            if '_delim' in head:
                del head['_delim']
            if '_DELIM' in head:
                del head['_DELIM']

        # remove _NROWS which make be there from a previous header read
        if '_NROWS' in head: del head['_NROWS']
        if '_nrows' in head: del head['_nrows']


        #s=pprint.pformat(head)
        #fobj.write(s)
        #fobj.write('\n')
        # As long as the dict contains types that can be represented as constants,
        # this pretty printing can be eval()d.
        pprint.pprint(head, stream=fobj)

        crap="""

        if delim is not None:
            _WriteDelim(fobj, delim)
        _WriteDescr(fobj, descr)

        if isinstance(header, dict):
            for k,v in header.items():
                if not isinstance(k,str):
                    mess='All header keyword names must be strings'
                    raise RuntimeError(mess)
                if isinstance(v,str):
                    v = "'"+v+"'"
                # Force to be lower
                k=k.lower()
                if k not in ['dtype','nrows','delim']:
                    fobj.write(k+' = '+str(v)+'\n')
        """

        fobj.write('END\n')
        fobj.write('\n')


def _WriteNrows(fobj, nrows):
    # Go to the beginning of the file
    fobj.seek(0)
    # Specially formatted for updating later
    out = 'NROWS = %20d\n' % (nrows,)
    fobj.write(out)

def _WriteDelim(fobj, delim):
    if delim == '\t':
        fobj.write("DELIM = '\\t'\n")
    else:
        fobj.write("DELIM = '%s'\n" % delim)

def _WriteDescr(fobj, descr):
    descr_strings = ['         '+str(d) for d in descr]
    descr_head = ', \\\n'.join(descr_strings)
    descr_head = '['+descr_head.strip()+']'
    fobj.write('DTYPE = '+descr_head+'\n')

def _WriteDescrOld(fobj, descr):
    fobj.write('DTYPE = '+str(descr)+'\n')

def _UpdateNrows(fobj, nrows_add):
    fobj.seek(0)
    hdr=read_header(fobj)
    nrows_current = _GetNrows(hdr)
    if nrows_current is None:
        raise RuntimeError('Attempting to update nrows but not found in header')
    nrows_new = nrows_current + nrows_add
    _WriteNrows(fobj, nrows_new)

       

def _GetNrows(header):
    if not isinstance(header,dict):
        raise RuntimeError('header must be a dict')

    nrows = _match_key(header,'_nrows')
    if nrows is not None:
        return int(nrows)
    else:
        raise RuntimeError('Header must contain the nrows keyword')

def _GetDtype(header):
    if not isinstance(header,dict):
        raise RuntimeError('header must be a dict')

    dtype = _match_key(header,'_dtype')
    if dtype is not None:
        return dtype
    else:
        raise RuntimeError('Header must contain the DTYPE keyword')


def _GetFobj(fileobj_input, major_mode, append=False):
    doappend=False

    fileobj= fileobj_input
    if isinstance(fileobj,(str,unicode)):

        # expand shortcut variables
        fileobj = os.path.expanduser(fileobj)
        fileobj= os.path.expandvars(fileobj)

        if major_mode == 'read':
            mode='r'
        else:
            if append:
                # make sure it actually exists first before trying to 
                # append
                if os.path.exists(fileobj):
                    doappend=True
                    mode="r+"
                else:
                    mode="w"
            else:
                mode="w"
        f_isstring = True
        fname_full = os.path.expanduser(fileobj)
        fobj = open(fname_full,mode)
    elif isinstance(fileobj,file):
        f_isstring = False
        fobj=fileobj
        if append:
            doappend=True
    else:
        raise RuntimeError('File must be a string or a file object')

    return fobj, f_isstring, doappend



def _remove_byteorder(descr):
    new_descr = []
    for d in descr:
        # d is a tuple, make it a list
        newd = list( copy.copy(d) )

        tdef = newd[1]
        tdef = tdef[1:]
        newd[1] = tdef
        newd = tuple(newd)
        new_descr.append(newd)

    return new_descr

def _get_rows2read(rows):
    if rows is None:
        r=None
        l=0
    else:
        r = numpy.array(rows,ndmin=1)
        l = r.size
    return r,l

def _get_fields2read(fields, dt):
    if fields is None:
        f=None
        l=0
    elif type(fields) == list:
        f=fields
        l=len(f)
    elif type(fields) == numpy.ndarray:
        f=fields
        l=len(f)
    elif type(fields) == str:
        f=[fields]
        l=len(f)
    else:
        raise ValueError('fields must be list,string or array')

    if f is not None:
        if not isinstance(f[0],str):
            # this is probably a list of column numbers, convert to strings
            allnames = [d[0] for d in dt]
            f = [allnames[i] for i in f]

    return f,l





def _match_fields(descr, fields):
    """

    For the fields that match the dtype, return arrays containing the sizes of
    each field and the offsets into the record

    """

    dtype = numpy.dtype(descr)
    allnames = dtype.names

    ntot = len(descr)

    field_offsets = []
    field_descr = []
    field_sizes = []

    # loop this way to preserve order
    i=0
    for name in allnames:
        if name in fields:
            fsize = dtype.fields[name][0].itemsize
            offset = dtype.fields[name][1]

            field_descr.append( descr[i] )
            field_offsets.append(offset)
            field_sizes.append(fsize)
        i += 1

    if len(field_offsets) == 0:
        raise ValueError("No field matched!")
    field_offsets=numpy.array(field_offsets, dtype='i8')
    field_sizes=numpy.array(field_sizes, dtype='i8')
    return field_descr, field_offsets, field_sizes

def recread(fobj, descr_or_dtype, fields, count, stripname=False, reset=False):
    """
    Read a subset of fields from binary file of fixed length records.
    This is the weave version, just been using it for testing.
    """

    import scipy.weave

    if isinstance(fields,(str,unicode)):
        fields=[fields]
    dtype = numpy.dtype(descr_or_dtype)

    field_descr, field_offsets, field_sizes = _match_fields(dtype.descr,fields)


    starting_pos = fobj.tell()
    filename = fobj.name


    if len(field_descr) == len(dtype.names):
        # all fields requested.  This is easy!
        output = numpy.fromfile(fobj, count=count, dtype=field_descr)

    else:

        recsize = dtype.itemsize

        # view as a char array and later re-view as a recarray
        field_dtype = numpy.dtype( field_descr )

        output = numpy.empty(count*field_dtype.itemsize, dtype='i1')

        # assume we are at the beginning of a record
        file_offset = starting_pos

        code="""
        int64_t row_index=0, field_index=0;
        int64_t offset=0, last_offset=0, last_fsize=0;
        int64_t seek_distance=0;
        int64_t fsize=0;
        int64_t nfields=0;

        char* ptr;
        FILE* fp;

        ptr = (char *) output_array->data;

        fp=fopen(filename.c_str(), "r");


        if (file_offset > 0) {
            fseek(fp, file_offset, SEEK_CUR);
        }

        // begin reading bytes
        // Loop over rows
        nfields = field_offsets.size();
        for (row_index=0; row_index<count; row_index++) {

            last_offset = 0;
            last_fsize = 0;

            for (field_index=0; field_index<nfields; field_index++) {

                // How far to we move before we read this data?
                offset  = field_offsets(field_index);
                seek_distance = offset-(last_offset + last_fsize);

                if (seek_distance > 0) {
                    fseek(fp, seek_distance, SEEK_CUR);
                }

                // Read the data
                fsize = field_sizes(field_index);
                fread(ptr, fsize, 1, fp);

                // On to the next field
                ptr += fsize;

                last_offset=offset;
                last_fsize=fsize;
            }

            // Do we need to move past any remaining fields?
            seek_distance = recsize - (last_offset+fsize);
            if (seek_distance > 0) {
                fseek(fp, seek_distance, SEEK_CUR);
            }

        }

        fclose(fp);
        """


        variables = ['filename','file_offset',
                     'field_offsets','field_sizes','recsize','count',
                     'output']
        scipy.weave.inline(code, variables,
                           type_converters = scipy.weave.converters.blitz)

        output = output.view( field_descr )


    if reset:
        fobj.seek(starting_pos)

    if len( field_descr ) == 1 and stripname:
        # for single fields we might want to just strip off the name
        name = field_descr[0][0]
        return output[name]
    else:
        return output


