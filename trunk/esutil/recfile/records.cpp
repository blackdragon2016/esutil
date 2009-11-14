#include "records.hpp"

/*
Records::Records() throw (const char*)
{
	InitializeVariables();
	import_array();
}

Records::Records(
		PyObject* file_obj, 
		const char* mode, 
		PyObject* delim_obj)
	throw (const char *)
{
	Open(file_obj, mode, delim_obj);
	import_array();
}

PyObject* Records::Open(
		PyObject* file_obj, 
		const char* mode, 
		PyObject* delim_obj) throw (const char*)
{
	PyObject* ret=NULL;
	ret = Py_None;
	Py_INCREF(Py_None);

	InitializeVariables();

	mMode=mode;
	GetFptr(file_obj, mMode.c_str());
	ProcessDelim(delim_obj);
	SetFileType();

	return ret;
}

*/

Records::Records(PyObject* fileobj, 
		const char* mode,
		PyObject* delimobj, 
		PyObject* dtype,
		long long nrows) throw (const char *)
{
	import_array();
	InitializeVariables();

	mMode=mode;
	GetFptr(fileobj, mMode.c_str());
	ProcessDelim(delimobj);
	SetFileType();

	if (mMode[0] == 'r') {
		if ( (dtype == NULL) || (nrows==-9999) ) {
			throw "You must send the datatype and number of rows when reading";
		}
		// Open for reading
		mAction=READ;
		ProcessDescr(dtype);
		ProcessNrows(nrows);
	} else {
		// Open for writing
		mAction=WRITE;
	}

}


Records::~Records() 
{

	// always decref; can be NULL but otherwise points to an input
	// type descriptor and we did an INCREF
	Py_XDECREF(mTypeDescr);

	// Always decref.  Either null or a new reference to mTypeDescr
	Py_XDECREF(mKeepTypeDescr);

	// This is also a copy
	Py_XDECREF(mRowsToRead);

	Close();

}

void Records::Close() throw (const char*)
{
	if (mFptrIsLocal && mFptr != NULL) {
		if (mDebug) DebugOut("Closing file");
		fclose(mFptr);
		mFptr=NULL;
	}
}


void Records::InitializeVariables()
{

	// First initialize all those pointers.  We must do this in case they
	// need to be decrefed; it will always decred if they are not null.

	// The type descriptor for each row of the file.  Will decref since we
	// increfed as we made a copy
	mTypeDescr=NULL;

	// Optional rows to read, default to all.  Using pyarray_converter in args,
	// so must DECREF this before returning.
	mRowsToRead=NULL;

	// The return object and data area pointer
	mReturnObject=NULL;
	mData=NULL;

	mFptr=NULL;
	mFptrIsLocal=false;

	mDelim="";

	// must be set later!!
	mAction=READ;
	mFileType = BINARY_FILE;

	mReadAsWhitespace=false;
	mReadWholeFileBinary=false;
	mReadWholeRowBinary=false;


	// Keep field stuff
	mKeepTypeDescr=NULL;

	mKeepNfields=0;

	mNrows=0;
	mNrowsToRead=0;

	return;

}

PyObject* Records::Read(
		PyObject* rows,
		PyObject* fields) throw (const char* )
{
	if (mFptr == NULL) {
		throw "File is not open";
	}
	if (mAction != READ) {
		throw "File is not open for reading";
	}

	ProcessRowsToRead(rows);
	ProcessFieldsToRead(fields);
	CreateOutputArray();
	ReadPrepare();

	ReadFromFile();

	return (PyObject* ) mReturnObject;
}



/*
PyObject* Records::Read(
		PyObject* descr, 
		long long nrows, 
		PyObject* rows,
		PyObject* fields) throw (const char* )
{
	if (mFptr == NULL) {
		throw "File is not open";
	}
	ProcessDescr(descr);
	ProcessNrows(nrows);
	ProcessRowsToRead(rows);
	ProcessFieldsToRead(fields);
	CreateOutputArray();
	ReadPrepare();

	ReadFromFile();

	return (PyObject* ) mReturnObject;
}
*/

void Records::ReadPrepare()
{
	if (mFileType == BINARY_FILE 
			&& mNrowsToRead == mNrows 
			&& mKeepNfields == mNfields) {

		mReadWholeFileBinary = true;
	} else if (mFileType == BINARY_FILE
			&& mKeepNfields == mNfields ) {

		mReadWholeRowBinary = true;
	} else if (mFileType == ASCII_FILE) {
		MakeScanFormats(true);
	}
}

void Records::ReadFromFile()
{
	if (mReadWholeFileBinary) {
		ReadAllAsBinary();
	} else {
		ReadRows();
	}
}

void Records::ReadAllAsBinary()
{
	if (mDebug) DebugOut("Reading all in one big fread()");
	int nread = fread(mData, mRowSize, mNrows, mFptr);
	if (nread != mNrows) {
		throw "Error reading entire file as binary";
	} 
}



// need to use long long
void Records::ReadRows()
{

	// Will hold row data if we are skipping rows (stored as array)
	npy_intp* rows=NULL;
	npy_intp current_row=0;
	npy_intp row2read=0;

	if (mNrowsToRead != mNrows) {
		// No data created or copied here
		rows = (npy_intp*) PyArray_DATA(mRowsToRead);
	}
	if (mDebug) DebugOut("Reading rows");

	// Loop over the rows to read, which could be a subset of the 
	// total number of rows in the file.
	for (npy_intp irow=0;  irow<mNrowsToRead; irow++) {
		if (mNrowsToRead != mNrows) {
			row2read=rows[irow];
		} else {
			row2read=irow;
		}

		// Skip rows?
		if (row2read > current_row) {
			SkipRows(current_row, row2read);
			current_row=row2read;
		} 

		ReadRow();
		current_row++;
	}


}




void Records::ReadRow()
{
	if (mReadWholeRowBinary) {
		// We can read a whole line if reading all fields
		ReadWholeRowBinary();
	} else {
		// Reading particular fields
		ReadFields();
	}
}

void Records::ReadFields()
{
	for (npy_intp fnum=0; fnum<mNfields; fnum++) {
		if (mKeep[fnum]) {
			ReadField(fnum);
		} else {
			SkipField(fnum);
		}
	}

}





void Records::ReadField(long long fnum)
{
	if (mFileType == BINARY_FILE) {
		ReadFieldAsBinary(fnum);
	} else {
		ReadFieldAsAscii(fnum);
	}
}




void Records::ReadFieldAsBinary(long long fnum)
{
	// Read the requested number of bytes
	int nread = fread(mData, mSizes[fnum], 1, mFptr);
	if (nread != 1) {
		string err="Error reading field: "+mNames[fnum];
		throw err.c_str();
	}
	// Move the data pointer
	mData = mData+mSizes[fnum];
}

void Records::ReadFieldAsAscii(long long fnum)
{

	if (mTypeNums[fnum] == NPY_STRING) {
		ReadAsciiBytes(fnum);
	} else {
		ScanVal(fnum);
		// For whitespace we haven't read the delimiter yet
		if (mReadAsWhitespace) {
			//char c = fgetc(mFptr);
			fgetc(mFptr);
		}
	}

	// Move the data pointer if we actually read this to the buffer
	if (mKeep[fnum]) {
		mData = mData+mSizes[fnum];
	}
}

void Records::ReadAsciiBytes(long long fnum)
{
	char c;
	char* buff;
	// If we are skipping this field just read into a different buffer
	if (mKeep[fnum]) {
		buff = mData;
	} else {
		//buff = &mBuffer[0];
		buff = (char *) mBuffer.c_str();
	}

	// Read the expected number of bytes *per element* as opposed to binary
	int size_per_el = mSizes[fnum]/mNel[fnum];

	// Loop over each element for ascii. Must do this because
	// of the delimters
	for (long long el=0; el<mNel[fnum]; el++) {

		for (long long i=0; i<size_per_el; i++) {
			c=fgetc(mFptr);
			if (c==EOF) {
				string err=
					"EOF reached unexpectedly reading field: "+
					mNames[fnum];
				throw err.c_str();
			}
			*buff = c;
			buff++;
		}

		// Read the delimiter or EOL
		c=fgetc(mFptr);

	}
}

void Records::ScanVal(long long fnum)
{

	char* buff;
	// If we are skipping this field just read into a different buffer
	if (mKeep[fnum]) {
		buff = mData;
	} else {
		//buff = &mBuffer[0];
		buff = (char *) mBuffer.c_str();
	}


	int type_num = mTypeNums[fnum];

	//{cout<<"  ScanVal with format: "<<mScanFormats[type_num].c_str()<<endl;
	//		fflush(stdout);}
	for (long long el=0; el<mNel[fnum]; el++) {
		int ret = fscanf(mFptr, mScanFormats[type_num].c_str(), buff);
		if (ret != 1) {
			string err="ScanVal: Error reading field: "+mNames[fnum];
			if (feof(mFptr)) {
				err += ": EOF reached unexpectedly";
			}
			else {
				err = + ": Read error";
			}
			throw err.c_str();
		}
		buff += mSizes[fnum]/mNel[fnum] ;
	}
}









void Records::SkipField(long long fnum)
{
	if (mFileType == BINARY_FILE) {
		SkipFieldAsBinary(fnum);
	} else {
		SkipFieldAsAscii(fnum);
	}
}

void Records::SkipFieldAsBinary(long long fnum)
{
	// Skip this field
	if(fseeko(mFptr, mSizes[fnum], SEEK_CUR) != 0) {
		string err="Error skipping field: "+mNames[fnum];
		throw err.c_str();
	}
}

// In this case we just call the read program since it knows about
// skipping
void Records::SkipFieldAsAscii(long long fnum)
{
	ReadFieldAsAscii(fnum);
}



void Records::ReadWholeRowBinary()
{
	int nread = fread(mData, mRowSize, 1, mFptr);
	if (nread != 1) {
		throw "Failed to read row data";
	}
	mData+=mRowSize;
}



void Records::SkipRows(long long current_row, long long row2read)
{
	long long rows2skip=0;
	if (mFileType == BINARY_FILE) {
		rows2skip = row2read-current_row;
		SkipBinaryRows(rows2skip);
	} else {
		if (mReadAsWhitespace) {
			rows2skip = row2read - current_row;// + 1;
		} else {
			rows2skip = row2read - current_row;
		}
		SkipAsciiRows(rows2skip);
	}
}



void Records::SkipAsciiRows(long long nskip)
{
	if (nskip > 0) {
		long long nlines = 0;
		char c;
		while (nlines < nskip) {
			c = fgetc(mFptr);
			if (c == EOF) {
				throw "Reached EOF prematurely";
			}
			if (c == '\n') {
				nlines++;
			}
		}
	}
}

void Records::SkipBinaryRows(long long nskip)
{
	if (nskip > 0) {
		if (fseeko(mFptr, mRowSize*nskip, SEEK_CUR) != 0) {
			throw "Failed to fseek";
		}
	}
}



void Records::CreateOutputArray()
{

	// this way we don't worry about freeing
	npy_intp d[1];
	PyArray_Dims shape;

	shape.ptr = d;
	shape.len = 1;


	if (mDebug) DebugOut("Creating output array");

	shape.ptr[0] = mNrowsToRead;

	if (mDebug) DebugOut("  Allocating");
	mReturnObject = (PyArrayObject* ) 
		PyArray_Zeros(
				1, 
				shape.ptr, 
				(PyArray_Descr *) mKeepTypeDescr, 
				NPY_FALSE);

	if (mReturnObject==NULL) {
		throw "Could not allocate array";
	}

	
	// Now the array has been created, and will not be XDECREFEd under
	// any circumstances.  This is so the user can see the state of the
	// array should any errors occur.  Thus we must also keep around the
	// descr.  Se we will add an extra reference so we can decref it later

	Py_INCREF(mKeepTypeDescr);

	// Make a pointer to the data area
	mData = mReturnObject->data;
}

PyObject* Records::Write(
		PyObject* obj, 
		bool padnull,
		bool ignorenull) throw (const char* )
{
	if (mFptr == NULL) {
		throw "File is not open";
	}
	if (mAction != WRITE) {
		throw "File is not open for writing";
	}

	PyObject* ret=Py_None;
	Py_INCREF(Py_None);


	if (!PyArray_Check(obj)) {
		throw "Input must be a NumPy array object";
	}
	mNrows = PyArray_Size(obj);

	PyArray_Descr* descr = PyArray_DESCR(obj);

	// Null characters in strings are converted to spaces
	mPadNull = padnull;
	mIgnoreNull = ignorenull;

	CopyFieldInfo(
			descr,
			mNames, 
			mOffsets,
			mSizes,
			mNel,
			mTypeNums,
			mRowSize);

	mNfields = mNames.size();

	mData = (char* ) PyArray_DATA(obj);

	if (mDebug) DebugOut("Writing data");
	if (mFileType == BINARY_FILE) {
		WriteAllAsBinary();
	} else{
		WriteRows();
	}

	if (mDebug) DebugOut("Finished writing");
	return(ret);
}

void Records::WriteAllAsBinary()
{
	// This is easy!
	if (mDebug) DebugOut("Writing in one big fwrite");
	npy_intp nwrite = fwrite(mData, mRowSize, mNrows, mFptr);
	if (nwrite < mNrows) {
		stringstream serr;
		string err;
		serr<<"Error occured writing binary data: Expected "
			<<mNrows<<" but only wrote "<<nwrite;

		err=serr.str();
		throw err.c_str();
	}

}

void Records::WriteRows()
{
	if (mDebug) {
		cout<<"Writing "<<mNrows<<" rows as ASCII"<<endl;
		fflush(stdout);
	}
	if (mDebug) DebugOut("Making print formats");
	MakePrintFormats();
	if (mDebug) DebugOut("Writing rows");
	for (long long row=0; row< mNrows; row++) {
		for (long long fnum=0; fnum< mNfields; fnum++) {

			long long nel=mNel[fnum];
			long long elsize = mSizes[fnum]/nel;

			for (long long el=0; el< nel; el++) {
				WriteField(fnum);
				mData += elsize;
			} // elements of this field
		} // fields
		// Write the newline character
		fputc('\n', mFptr);
	} // rows
}

void Records::WriteField(long long fnum) 
{
	if (mTypeNums[fnum] == NPY_STRING) {
		WriteStringAsAscii(fnum);
	} else {
		WriteNumberAsAscii(mData, mTypeNums[fnum]);
	}
	if ( fnum < (mNfields-1) ) {
		fprintf(mFptr, "%s", mDelim.c_str());
	}
}

void Records::WriteStringAsAscii(long long fnum)
{
	char* buffer=NULL;

	buffer = mData;

	long long slen = mSizes[fnum]/mNel[fnum];
	for (long long i=0; i<slen; i++) {
		char c=buffer[0];
		if (c == '\0') {
			if (mIgnoreNull) {
				// we assume the user cares about nothing beyond the null
				// this will break out of writing this the rest of this field.
				break;
			}
			if ( mPadNull ) {
				c=' ';
			}
		}
		int res = fputc( (int) c, mFptr);
		if (res == EOF) {
			throw "Error occured writing string field";
		}
		buffer++;
	}
}

void Records::WriteNumberAsAscii(char* buffer, long long type)
{
	int res;

	switch (type) {
		case NPY_INT8:
			res= fprintf( mFptr, 
					mPrintFormats[type].c_str(), *(npy_int8* )buffer ); 	
			break;
		case NPY_UINT8:
			res= fprintf( mFptr, 
					mPrintFormats[type].c_str(), *(npy_uint8* )buffer ); 	
			break;

		case NPY_INT16:
			res= fprintf( mFptr, 
					mPrintFormats[type].c_str(), *(npy_int16* )buffer ); 	
			break;
		case NPY_UINT16:
			res= fprintf( mFptr, 
					mPrintFormats[type].c_str(), *(npy_uint16* )buffer ); 	
			break;

		case NPY_INT32:
			res= fprintf( mFptr, 
					mPrintFormats[type].c_str(), *(npy_int32* )buffer ); 	
			break;
		case NPY_UINT32:
			res= fprintf( mFptr, 
					mPrintFormats[type].c_str(), *(npy_uint32* )buffer ); 	
			break;

		case NPY_INT64:
			res= fprintf( mFptr, 
					mPrintFormats[type].c_str(), *(npy_int64* )buffer ); 	
			break;
		case NPY_UINT64:
			res= fprintf( mFptr, 
					mPrintFormats[type].c_str(), *(npy_uint64* )buffer ); 	
			break;

#ifdef NPY_INT128
		case NPY_INT128:
			res= fprintf( mFptr, 
					mPrintFormats[type].c_str(), *(npy_int128* )buffer ); 	
			break;
		case NPY_UINT128:
			res= fprintf( mFptr, 
					mPrintFormats[type].c_str(), *(npy_uint128* )buffer ); 	
			break;
#endif
#ifdef NPY_INT256
		case NPY_INT256:
			res= fprintf( mFptr, 
					mPrintFormats[type].c_str(), *(npy_int256* )buffer ); 	
			break;
		case NPY_UINT256:
			res= fprintf( mFptr, 
					mPrintFormats[type].c_str(), *(npy_uint256* )buffer ); 	
			break;
#endif

		case NPY_FLOAT32:
			res= fprintf( mFptr, 
					mPrintFormats[type].c_str(), *(npy_float32* )buffer ); 	
			break;
		case NPY_FLOAT64:
			res= fprintf( mFptr, 
					mPrintFormats[type].c_str(), *(npy_float64* )buffer ); 	
			break;
#ifdef NPY_FLOAT128
		case NPY_FLOAT128:
			res= fprintf( mFptr,
					mPrintFormats[type].c_str(),*(npy_float128* )buffer ); 	
			break;
#endif

		default:
			stringstream serr;
			string err;
			serr << "Unsupported type "<<type;
			err=serr.str();
			throw err.c_str();
			break;
	}

	if (res < 0) {
		throw "Error writing data";
	}
}






void Records::ProcessFieldsToRead(PyObject* fields)
{

	if (mDebug) DebugOut("Processing requested fields");
	mKeep.resize(mNfields, 0);
	if (fields == NULL || fields == Py_None) {
		mKeepNfields = mNfields;
		mKeepId.resize(mNfields);
		for (long long i=0; i<mNfields; i++) {
			mKeepId[i] = i;
		}
		mKeepTypeDescr = mTypeDescr;
		Py_INCREF(mTypeDescr);
	} else {
		SubDtype(mTypeDescr, fields, &mKeepTypeDescr, mKeepId);
		mKeepNfields = mKeepId.size();
	}

	// This tells us if we keep a given field
	if (mDebug) DebugOut("Setting mKeep vector");
	for (long long i=0; i<mKeepNfields; i++) {
		mKeep[ mKeepId[i] ] = 1;
	}

	if (mDebug) {
		cout<<"Will read "<<mKeepNfields<<"/"<<mNfields<<" fields"<<endl;
		fflush(stdout);
	}

}

void Records::ProcessRowsToRead(PyObject* rows)
{
	// Convert to an array of the desired type.  We will xdecref this 
	mRowsToRead = Object2IntpArray(rows);
	if (mRowsToRead == NULL) {
		// If returns NULL and no excepton thrown, means we will read all
		mNrowsToRead = mNrows;
	} else {
		// How many to read
		mNrowsToRead = PyArray_SIZE(mRowsToRead);
	}

	if (mDebug) {
		cout<<"Will read "<<mNrowsToRead<<"/"<<mNrows<<" rows"<<endl;
		fflush(stdout);
	}
}


void Records::ProcessNrows(long long nrows) 
{
	if (mDebug) {cout<<"nrows = "<<nrows<<endl;fflush(stdout);}
	if (nrows < 1) {
		throw "Input nrows must be >= 1";
	}
	mNrows = nrows;
}

void Records::ProcessDescr(PyObject* descr)
{
	if (descr == NULL) {
		throw "Input descr is NULL";
	}

	if (!PyArray_DescrCheck(descr)) {
		throw
			"Input descr must be a NumPy type descriptor. e.g. "
			"arr.dtype, or numpy.dtype(typelist)";
	}

	// Get a new reference to this descr and make sure to decref later
	// on destruction
	mTypeDescr = descr;
	Py_XINCREF(descr);

	// Copy info for each field into a simpler form
	CopyFieldInfo(
			(PyArray_Descr* ) mTypeDescr,
			mNames, 
			mOffsets,
			mSizes,
			mNel,
			mTypeNums,
			mRowSize);

	// Each vector should now be number of fields long
	mNfields = mNames.size();
}


void Records::GetFptr(PyObject* file_obj, const char* mode)
{
	if (mDebug) DebugOut("Getting fptr");

	// The file_obj is a string
	if (PyString_Check(file_obj)) {

		string fstr=PyString_AsString(file_obj);
		mFptr = fopen(fstr.c_str(), mode);
		if (mFptr==NULL) {
			string err="Could not open file: "+fstr;
			throw err.c_str();
		}
		mFptrIsLocal=true;
		return;
	} else if (PyFile_Check(file_obj)) {

		mFptr = PyFile_AsFile(file_obj);
		if (mFptr==NULL) {
			throw "File object is invalid";
		}
		mFptrIsLocal=false;
		return;
	} else {
		throw "Input must be a file object or a string";
	}
}

void Records::ProcessDelim(PyObject* delim_obj)
{
	if (delim_obj == NULL) {
		mDelim="";
	} else {
		if (PyString_Check(delim_obj)) {
			mDelim = PyString_AsString(delim_obj);
		} else {
			throw "delim keyword must be a string"; 
		}
	}

	if (mDelim[0] == ' ') {
		mReadAsWhitespace=true;
	} else {
		mReadAsWhitespace=false;
	}

	if (mDebug) {cout<<"Using delim = \""<<mDelim<<"\""<<endl; fflush(stdout);}
}

void Records::SetFileType()
{
	if (mDelim == "") {
		mFileType = BINARY_FILE;
		if (mDebug) DebugOut("File type set to BINARY_FILE");
	} else {
		mFileType = ASCII_FILE;
		if (mDebug) DebugOut("File type set to ASCII_FILE");
	}

}




// given a numpy  PyArray_Descr* and a list of field names return a new
// type descriptor containing only the subset
void Records::SubDtype(
		PyObject* indescr, 
		PyObject* subnamesobj,
		PyObject** newdescr,
		vector<long long>& matchids) {

	PyArray_Descr* descr=(PyArray_Descr* ) indescr;
	vector<string> names;

	// make string vector
	CopyDescrOrderedNames(descr, names);

	// This makes sure they end up in the original order: important
	// for skipping fields and such
	
	// First deal with a scalar string or list input
	if (PyList_Check(subnamesobj)) {
		ListStringMatch(names, subnamesobj, matchids);
	} else if (PyString_Check(subnamesobj)) {
		// Must decref
		PyObject* tmplist = PyList_New(0);
		// Makes a copy on append.
		PyList_Append(tmplist, subnamesobj);
		ListStringMatch(names, tmplist, matchids);
		Py_XDECREF(tmplist);
	} else {
		throw "fields keyword must be string or list";
	}
	vector<string> matchnames;
	matchnames.resize(matchids.size());
	for (unsigned long long i=0; i<matchids.size(); i++) {
		matchnames[i] = names[matchids[i]];
	}

	// Now based on the matches create a new dtype
	*newdescr = ExtractSubDescr(descr, matchnames);

}




// Extract a subset of the fields from a PyArray_Descr and return a new
// descr with that info
PyObject* Records::ExtractSubDescr(
		PyArray_Descr* descr, 
		vector<string>& names)
{

	PyArray_Descr *fdescr=NULL;
	char* title=NULL;
	long long offset;

	PyObject* dlist=PyList_New(0);
	PyArray_Descr* newdescr=NULL;

	if (mDebug) {cout<<"Extracting sub descr"<<endl;fflush(stdout);}
	for (unsigned long long i=0; i<names.size(); i++) {
		PyObject* item=
			PyDict_GetItemString(descr->fields, names[i].c_str());

		if (item!=NULL) {
			if (!PyArg_ParseTuple(item, "Oi|O", &fdescr, &offset, &title)) {
				if (mDebug) 
				{cout<<"Field: "<<names[i]<<" not right format"<<endl;}
			} else {

				PyObject* tup = 
					FieldDescriptorAsTuple(fdescr, names[i].c_str());

				// copy is made of tuple
				if (PyList_Append(dlist, tup) != 0) {
					throw "Could not append to list";
				}
				Py_XDECREF(tup);

			}
		} else {
			if (mDebug) 
			{cout<<"field: "<<names[i]<<" does not exist. offset->-1"<<endl;}
		}
	}

	// Now convert this list to a descr
	if (mDebug) {cout<<"Converting list to descr"<<endl;fflush(stdout);}
	if (!PyArray_DescrConverter(dlist, &newdescr)) {
		throw "data type not understood";
	}
	if (mDebug) {cout<<"  Done"<<endl;fflush(stdout);};

	return( (PyObject* )newdescr);
}








// Copy some info from a fields["fname"].descr into a tuple
// This will become part of a list of tuples dtype send to the converter
PyObject* Records::FieldDescriptorAsTuple(PyArray_Descr* fdescr, const char* name)
{
	// Use a string stream to convert all the char and possible int
	// elements of a type string
	stringstream typestream (stringstream::in | stringstream::out);
	string typestring;

	long long nel=0, tupsize=0;
	PyObject* shape=NULL;
	if (fdescr->subarray != NULL) {
		// This is a sub-array and requires the tuple to have a
		// length specified Here we are implicitly only allowing
		// subarrays if basic numbers or strings

		typestream << fdescr->subarray->base->byteorder;
		typestream << fdescr->subarray->base->type;
		//typestring[0] = fdescr->subarray->base->byteorder;
		//typestring[1] = fdescr->subarray->base->type;
		if (fdescr->subarray->base->type_num == NPY_STRING) {
			//typestring += itoa(fdescr->subarray->base->elsize);
			typestream << fdescr->subarray->base->elsize;
		}
		nel = fdescr->elsize/fdescr->subarray->base->elsize;

		// Need to incref this because the PyTuple_SetItem will
		// steal a referenc
		shape = fdescr->subarray->shape;
		tupsize=3;
	} else {
		//typestring[0] = fdescr->byteorder;
		//typestring[1] = fdescr->type;
		typestream << fdescr->byteorder;
		typestream << fdescr->type;
		if (fdescr->type_num == NPY_STRING) {
			//typestring += itoa(fdescr->elsize);
			typestream << fdescr->elsize;
		}
		nel = 1;
		tupsize=2;
	}

	typestream >> typestring;

	// A copy is made when inserting into the list 
	// so we need to decref this
	PyObject* tup=PyTuple_New(tupsize);

	// In setitems references are stolen, so better to just
	// put the expressions in there than possibly worry later
	// about references
	PyTuple_SetItem(
			tup,
			0,
			PyString_FromString(name) );
	PyTuple_SetItem(
			tup,
			1,
			PyString_FromString(typestring.c_str()) );

	if (tupsize == 3) {
		PyTuple_SetItem(
				tup,
				2,
				shape);
		Py_XINCREF(shape);
	}

	if (mDebug) {
		cout<<"("
			<<"'"
			<<PyString_AsString(PyTuple_GetItem(tup,0))<<"'"
			<<", '"
			<<PyString_AsString(PyTuple_GetItem(tup,1))<<"'";
		if (nel > 1) {
			cout <<", "<<nel;
		}
		cout <<")"<<endl;
	}



	return(tup);

}


// Must decref this arr no matter what. Use Py_XDECREF in case it
// is NULL
// AHHHHH!!!!  On my macbook core 2 duo, which is 64-bit, intp is 32-bit!!! Can't 
// figure out how to make it use 64-bit
PyObject* Records::Object2IntpArray(PyObject* obj)
{

	// NPY_DEFAULT is currently NPY_CARRAY
	int min_depth=0, max_depth=0, flags=NPY_DEFAULT;
	PyObject* arr=NULL;

	if (obj == NULL || obj == Py_None) {
		return NULL;
	}

	PyArray_Descr* descr=NULL;
	descr = PyArray_DescrNewFromType(NPY_INTP);

	if (descr == NULL) {
		throw "could not create NPY_INPT descriptor";
	}
	// This will steal a reference to descr, so we don't need to decref
	// descr as long as we decref the array!
	arr = PyArray_FromAny(obj, descr, min_depth, max_depth, flags, NULL);
	if (arr == NULL) {
		throw "Could not convert rows keyword to an array of type NPY_INTP";
	}
	return arr;
}



void Records::ListStringMatch(
		vector<string> snames,
		PyObject* list, 
		vector<long long>& matchids)
{

	if (mDebug) {cout<<"Matching fields to subfields"<<endl;fflush(stdout);}
	long long len=SequenceCheck(list);

	matchids.clear();
	if (len <= 0) {
		// Just return all
		matchids.resize(snames.size());
		for (unsigned long long i=0; i<matchids.size(); i++)
		{
			matchids[i] = i;
		}
	} else {
		// Get strings from list.
		vector<string> goodones;
		for (long long i=0; i<len; i++) {
			PyObject* item = PySequence_GetItem(list, i);
			if (!PyString_Check(item)) {
				cout<<"fields["<<i<<"] is not a string; skipping"<<endl;
				fflush(stdout);
			} else {
				string ts = PyString_AsString(item);
				goodones.push_back(ts);
			}
		}
		if (goodones.size() == 0) {
			throw "None of the requested fields are in string form";
		} else {
			// loop over snames and see which ones match the input list
			// this preserves order, which is important.
			for (unsigned long long i=0; i<snames.size(); i++) {
				string name=snames[i];
				// See if there is a match
				vector<string>::iterator matchel;
				matchel = find(goodones.begin(),goodones.end(),name);
				if (matchel != goodones.end()) {
					matchids.push_back(i);
				}
			}
		}
	}
	if (matchids.size() == 0) {
		throw "None of the requested field names matched";
	}

}

long long Records::SequenceCheck(PyObject* obj)
{
	if (obj == NULL) {
		return -1;
	}
	long long len=0;
	// The docs claim this check always succeeds, but not on NULL
	if (PySequence_Check(obj)) {
		len=PySequence_Size(obj);
	} else {
		len=-1;
	}
	return len;

}

void Records::DebugOut(const char* mess)
{
	cout<<mess<<endl;
	fflush(stdout);
}

PyObject* Records::Test()
{

	FILE* fptr;
	fptr = mFptr;
	mFptr = stdout;

	npy_float32 f32=-3.3123423e15;
	npy_float64 f64=1.234312341324e-16;

	npy_int32 i32 = 1234141;
	npy_int64 i64 = 83234321;

	char* p;


	printf("Trying WriteNumberAsAscii()\n\n");
	MakePrintFormats();


	printf("\n\ti32 = ");
	p = (char *) &i32;
	WriteNumberAsAscii(p, NPY_INT32);
	printf("\n\ti64 = ");
	p = (char *) &i64;
	WriteNumberAsAscii(p, NPY_INT64);
	printf("\n\tf32 = ");
	p = (char *) &f32;
	WriteNumberAsAscii(p, NPY_FLOAT32);
	printf("\n\tf64 = ");
	p = (char *) &f64;
	WriteNumberAsAscii(p, NPY_FLOAT64);


	printf("\n\n");

	mFptr=fptr;

	return PyLong_FromLong(0);
}

void Records::PyDictPrintKeys(PyObject* dict)
{
	PyObject* keys = PyDict_Keys(dict);

	long long len=SequenceCheck(keys);
	for (long long i=0; i<len; i++) {
		PyObject* item = PyList_GetItem(keys, i);
		cout<<"key["<<i<<"] = "<<PyString_AsString(item)<<endl;
		Py_XDECREF(item);
	}

	Py_XDECREF(keys);
	fflush(stdout);
}


// These get functions do not rely on internal data
void Records::CopyFieldInfo(
		PyArray_Descr* descr, 
		vector<string>& names, 
		vector<long long>& offsets,
		vector<long long>& sizes,
		vector<long long>& nel,
		vector<long long>& typenums,
		long long& rowsize)
{
	if (mDebug) DebugOut("Copying field info");
	CopyDescrOrderedNames(descr, names);
	CopyDescrOrderedOffsets(descr, names, offsets, sizes, nel, typenums);
	rowsize = descr->elsize;
}

void Records::CopyDescrOrderedNames(
		PyArray_Descr* descr, 
		vector<string>& names)
{
	// Get the ordered names
	names.resize(0);

	for (long long i=0; i<PyTuple_Size(descr->names); i++) {
		PyObject* tmp = PyTuple_GET_ITEM(descr->names, i);
		string tname=PyString_AS_STRING(tmp);
		if (mDebug) {cout<<"  "<<tname<<endl;}
		names.push_back(tname);
	}

}

void Records::CopyDescrOrderedOffsets(
		PyArray_Descr* descr, 
		vector<string>& names,
		vector<long long>& offsets,
		vector<long long>& sizes,
		vector<long long>& nel,
		vector<long long>& typenums)
{
	offsets.clear();
	offsets.resize(names.size(), -1);
	sizes.clear();
	sizes.resize(names.size(), -1);
	typenums.clear();
	typenums.resize(names.size(), -1);
	nel.clear();
	nel.resize(names.size(), -1);

	// Get the offsets, ordered with names
	PyArray_Descr *fdescr, *title;

	// WARNING:  this is long int and being copied to long long
	long int offset;

	if (mDebug) {cout<<"Copying ordered descr info:"<<endl;fflush(stdout);}
	for (unsigned long long i=0; i<names.size(); i++) {
		PyObject* item=
			PyDict_GetItemString(descr->fields, names[i].c_str());

		if (item!=NULL) {
			if (!PyArg_ParseTuple(item, "Ol|O", &fdescr, &offset, &title)) {
				if (mDebug) 
				{cout<<"Field: "<<names[i]<<" not right format"<<endl;}
			}
			else {
				offsets[i] = offset;
				sizes[i] = fdescr->elsize;
				typenums[i] = fdescr->type_num;
				if (fdescr->subarray != NULL) {
					// Here we are implicitly only allowing subarrays
					// if basic numbers or strings
					nel[i] = sizes[i]/fdescr->subarray->base->elsize;
					typenums[i] = fdescr->subarray->base->type_num;
				} else {
					nel[i] = 1;
				}
				if (mDebug) {
					cout<<"  Offset("<<names[i]<<"): "<<offset<<endl;
					cout<<"  Size("<<names[i]<<"): "<<sizes[i]<<endl;
					cout<<"  nel("<<names[i]<<"): "<<nel[i]<<endl;
					cout<<"  type_num("<<names[i]<<"): "<<typenums[i]<<endl;
					cout<<"  type("<<names[i]<<"): "<<fdescr->type<<endl;
					cout<<endl;
				}
			}
		} else {
			if (mDebug) 
			{cout<<"field: "<<names[i]<<" does not exist. offset->-1"<<endl;}
		}
	}

	if (mDebug) DebugOut("  Done");
}


void Records::MakeScanFormats(bool add_delim)
{

	mScanFormats.clear();
	int nf=24;
	mScanFormats.resize(nf, "%");

	mScanFormats[NPY_INT8] += NPY_INT8_FMT;
	mScanFormats[NPY_UINT8] += NPY_UINT8_FMT;
	
	mScanFormats[NPY_INT16] += NPY_INT16_FMT;
	mScanFormats[NPY_UINT16] += NPY_UINT16_FMT;

	mScanFormats[NPY_INT32] += NPY_INT32_FMT;
	mScanFormats[NPY_UINT32] += NPY_UINT32_FMT;

	mScanFormats[NPY_INT64] += NPY_INT64_FMT;
	mScanFormats[NPY_UINT64] += NPY_UINT64_FMT;

#ifdef NPY_INT128
	mScanFormats[NPY_INT128] += NPY_INT128_FMT;
	mScanFormats[NPY_UINT128] += NPY_UINT128_FMT;
#endif
#ifdef NPY_INT256
	mScanFormats[NPY_INT256] += NPY_INT256_FMT;
	mScanFormats[NPY_UINT256] += NPY_UINT256_FMT;
#endif

	// They put %g for these..!!??
	mScanFormats[NPY_FLOAT] += "f";
	mScanFormats[NPY_DOUBLE] += "lf";

#ifdef NPY_LONGDOUBLE
	mScanFormats[NPY_LONGDOUBLE] += "Lf";
#endif

	// The types for long long integers are incorrect in the
	// ndarrayobject.h header.  Uses Ld instead of lld.  
	// We need to loop over and fix this since we don't know ahead
	// of time on this platform which is the lld type
	for (int i=0; i<nf; i++) {
		if (mScanFormats[i] == "%Ld") {
			mScanFormats[i] = "%lld";
		}
		if (mScanFormats[i] == "%Lu") {
			mScanFormats[i] = "%llu";
		}
	}

	// Only add in the 
	if ((!mReadAsWhitespace) && (add_delim) ) {
		for (int i=0; i<nf; i++) {
			if (mScanFormats[i] != "%") {
				mScanFormats[i] += ' '+mDelim;
			}
		}
	}
}

void Records::MakePrintFormats()
{

	MakeScanFormats(false);

	mPrintFormats.clear();
	mPrintFormats.assign( mScanFormats.begin(), mScanFormats.end() );
	
	mPrintFormats[NPY_FLOAT] = "%g";
	mPrintFormats[NPY_DOUBLE] = "%15.8e";

	mPrintFormats[NPY_STRING] = "%s";

}


