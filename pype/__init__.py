# These are classes and functions for loading
# and processing transliterated tablets.

import sys
import re
import bz2
from collections import namedtuple
from collections import defaultdict

transliterationsPath = "./data/cdli_atf_20180602.txt.bz2"
provenancePath = "./data/provenance.bz2"
normalizeCharactersRegex = "#|~[a-zA-Z0-9]+|@[a-zA-Z0-9]+"

class Tablet( object ):
    def __init__( self, cdliNo, primarySource, header, faces, sealed = False ):
        self.cdliNo        = cdliNo
        self.primarySource = primarySource
        self.header        = header
        self.faces         = faces
        self.sealed        = sealed

    def __str__( self ):
        s = self.cdliNo + ":\n"
        for f in self.faces:
            for col in self.faces[f]:
                for entry in self.faces[f][col]:
                    s += "\t"+str(entry)+"\n"
        return s

    def getHeader( self ):
        if self.header:
            face, col, line = self.header
            return self.faces[face][col][line]

    def getLines( self, excludeHeader = False, excludeNumeric = True ):
        for face in self.faces:
            for column in self.faces[face]:
                for line,_ in enumerate(self.faces[face][column]):
                    # Skip the header if desired:
                    if (face, column, line) == self.header and excludeHeader is True:
                        continue
                    text, number = self.faces[face][column][line]
                    # Make sure text is not none so we don't return empty lines.
                    if excludeNumeric and text is not None:
                        yield text
                    # NOTE Caller should be aware that number might be None.
                    elif not excludeNumeric:
                        yield text, number
                    else:
                        pass
        
    def linearize( self, excludeNumeric = True ):
        linearized = ""
        if excludeNumeric:
            for line in self.getLines( excludeNumeric = True ):
                if line is not None:
                    linearized += " " + line
            return linearized[1:]
          
        for (line,num) in self.getLines( excludeNumeric = False ):
            if line is not None:
                line = line.split()
                line = ' '.join([(format_numeric_sign(s) if 'N' in s and '+' not in s else s) for s in line])
                linearized += " " + line
            if num is not None:
                num = num.split()
                for n_sign in num:
                    try:
                        n = get_count( n_sign )
                        n_sign = format_numeric_sign( n_sign )
                        linearized += n * (" " + n_sign)
                    except ValueError:
                        n_sign = format_numeric_sign( n_sign )
                        linearized += " " + n_sign
        return linearized[1:]

def loadProvenance( path ):
    f = bz2.open( path, 'r' )
    prov = f.read().decode("utf-8")
    f.close()
    
    prov = prov.split("\n")[:-1]
    prov = [line.split("\t") for line in prov]
    prov_dict = {p[1]:p[0] for p in prov}
    
    return prov_dict
        
def loadCorpus( path ):
    f = bz2.open( path, 'r' )
    corpus = f.read().decode("utf-8")
    f.close()

    corpus = corpus.split("\n\n\n")[:-1]
    tablets = []
    for tablet in corpus:
        tablet        = tablet.split("\n")
        faces         = defaultdict(lambda:defaultdict(lambda:[]))
        currentFace   = None
        columnNo      = 0
        lineNo        = 0
        cdliNo        = None
        primarySource = None
        header        = None
        lastLine      = None
        lineNoPattern = "^[0-9]+(\.?[a-zA-Z0-9]+)?\??'?\."
        sealed        = False

        for line in tablet:

            line = line.strip()
            if cdliNo == 'P008227':
              #print("DEBUG:",line)
              pass

            if line == "":
                continue

            elif line == "# header":
                header = lastLine
                if header == None:
                    print( "WARNING: empty header?" )

            # This ignores many of the comments in the transliteration, eg regarding
            # erasures. Could have a "comments" field for each tablet to keep track
            # of these if they're ever needed.
            elif line.startswith("@seal") or line.startswith("$ seal"):
                sealed = True

            elif line == "@tablet" or line.startswith("$") or line.startswith("#"):
                continue

            elif line.startswith("&"):
                cdliNo, primarySource = line[1:].split(" = ")

            elif line in ["@obverse", "@reverse", "@top", "@left"]:
                 currentFace = line

            elif line.startswith("@column"):
                # Subtract 1 from CDLI column no. so that everything is zero-indexed.
                columnNo = int( line.split()[1] ) - 1
                # Reset line number to beginning of the column/to where we left off on this column (in case of fragments)
                lineNo = len( faces[currentFace][columnNo] )

            elif line.startswith( "@fragment" ):
                # There is only one fragment in the whole corpus. 
                # We just pretend the lines in the fragment are still
                # attached to the rest of the tablet for simplicity.
                pass

            elif ',' in line:
                if line.count(",") > 1:
                    # TODO Check with Kate about these lines. Just treat the multiple numeric
                    # parts as a single number? Or record them separately? For the line with 
                    # non-numeric glyphs separated by commas, treat this as a single entry?
                    # Might be safe to ignore this last one, because it looks pretty fragmentary.
                    continue
                text, number = line.split(",")
                text = re.sub( lineNoPattern, "", text.strip() ).strip()
                number = number.strip()
                if number == "" and "N" in text:
                    # TODO Looks like these are cases where the sum was transliterated before the comma rather than after. Is this right?
                    number = text
                    text = None
                lastLine = (currentFace, columnNo, lineNo)
                if text is not None:
                  text = text.upper()
                if number is not None:
                  number = number.upper()
                faces[currentFace][columnNo] += [(text, number)]
                lineNo += 1

            else:
                # Line with no comma = just a number or just some signs without a count.
                # Looks like these are usually headers or final sums.
                line = re.sub( lineNoPattern, "", line ).strip()
                if line == "":
                    # If a line is present in the transliteration but it is empty, then don't record it here. 
                    # TODO Should probably still append an empty line to the tablet, so that our line numbers
                    # match the line numbers in the transliteration (for easy grepping, eg)
                    continue
                if "M" in line and "N" in line:
                    # TODO I'm assuming these lines are mis-transliterated, and someone just forgot to write the ,
                    # Check with Kate to make verify whether this is correct.
                    line = line.split(" ")
                    try:
                        split = ["N" in c and "M" not in c for c in line].index(True)
                        text, number = ' '.join(line[:split]), ' '.join(line[split:])
                    except ValueError:
                        text, number = ' '.join(line), None
                elif "M" in line:
                    text, number = line, None
                elif "N" in line:
                    text, number = None, line
                else:
                    # Lines with no transliterated characters (just [...], x, etc)
                    text, number = line, None
                lastLine = (currentFace, columnNo, lineNo)
                if text is not None:
                  text = text.upper()
                if number is not None:
                  number = number.upper()
                faces[currentFace][columnNo] += [(text, number)]
                lineNo += 1
                
        tablets += [Tablet( cdliNo, primarySource, header, faces, sealed=sealed )]
        
    return tablets

def normalize( character ):
    # TODO What do the different notations mean? Check that these are all supposed to collapse into one sign group:
    # N24@b
    # M218~d
    # M072#
    # TODO Is N30D different from N30 or just a variant? 
    return re.sub( normalizeCharactersRegex, "", character ).replace("?","")

def format_numeric_sign( sign ):
    # Remove number of occurrences from a numeric sign.
    return re.sub( r'.*\((N.*)\).*', r'\1', sign )

def get_count( sign ):
    # Get the number of repetitions of a numeric sign,
    # eg given 2(N01) returns 2.
    return int(re.sub( r'(\d+)\(.*', r'\1', sign ))

provenances = loadProvenance( provenancePath )
tablets = loadCorpus( transliterationsPath )

def ngrams( n, normalizeSigns = False, excludeHeader = False, excludeNumeric = True, excludeCorrections = True, overlapEntryAndNumeric=False ):
    grams = defaultdict(int)

    for j,tablet in enumerate(tablets):
        for i,line in enumerate(tablet.getLines( excludeHeader, excludeNumeric )):

            if not excludeNumeric:
                text, number = line
                if number is not None and number != "":
                    number = number.split()
                    number_expanded = []
                    for sign in number:
                        try:
                            count = get_count( sign )
                            sign = format_numeric_sign( sign )
                            # Expand signs like 2(N01) into explicit strings "N01 N01"
                            number_expanded += [ sign for _ in range(count) ]
                        except:
                            number_expanded += [ sign ]
                    number = ' '.join( number_expanded )
                    if text is not None:
                        line = text.strip() + ' ' + number
                    else:
                        line = number
                else:
                    line = text
            line = line.split()
            # Remove [ and ] so that eg [M288] is not counted as a different sign from M288.
            # TODO Is it reasonable to just remove ? here as well? Or have this as a configurable
            # parameter?
            line = [ re.sub( "\#|\[|\]|\?", "", sign ) for sign in line ]
            line = [ (format_numeric_sign(sign) if 'N' in sign and '+' not in sign else sign) for sign in line ]
            # Collapse sign variants into a single sign group.
            if normalizeSigns:
                line = [ normalize( sign ) for sign in line ]
            # Exclude signs containing <> or !.
            # These are corrections by modern editors.
            if excludeCorrections:
                line = [ sign if ( not sign.startswith("<") or not sign.endswith(">") ) and not sign.endswith("!") else "x" for sign in line ]
            else:
                line = [ sign.replace("<","").replace(">","").replace("!","") for sign in line ]
            line = tuple( line )

            for start in range( 0, len(line) - n + 1 ):
                gram = line[start:start + n]
                grams[gram] += 1

    grams = {sign:grams[sign] for sign in grams if 'x' not in sign and 'X' not in sign and '...' not in sign}
    return grams
