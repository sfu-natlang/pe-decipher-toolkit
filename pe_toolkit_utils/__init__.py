# The log_progress method is copyright 2016 bureaucratic-labs and is included
# here under the terms of the MIT License. 
# 
# See https://github.com/kuk/log-progress
# 
# MIT License
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

def log_progress(sequence, every=None, size=None, name='Items'):
    from ipywidgets import IntProgress, HTML, VBox
    from IPython.display import display

    is_iterator = False
    if size is None:
        try:
            size = len(sequence)
        except TypeError:
            is_iterator = True
    if size is not None:
        if every is None:
            if size <= 200:
                every = 1
            else:
                every = int(size / 200)     # every 0.5%
    else:
        assert every is not None, 'sequence is iterator, set every'

    if is_iterator:
        progress = IntProgress(min=0, max=1, value=1)
        progress.bar_style = 'info'
    else:
        progress = IntProgress(min=0, max=size, value=0)
    label = HTML()
    box = VBox(children=[label, progress])
    display(box)

    index = 0
    try:
        for index, record in enumerate(sequence, 1):
            if index == 1 or index % every == 0:
                if is_iterator:
                    label.value = '{name}: {index} / ?'.format(
                        name=name,
                        index=index
                    )
                else:
                    progress.value = index
                    label.value = u'{name}: {index} / {size}'.format(
                        name=name,
                        index=index,
                        size=size
                    )
            yield record
    except:
        progress.bar_style = 'danger'
        raise
    else:
        progress.bar_style = 'success'
        progress.value = index
        label.value = "{name}: {index}".format(
            name=name,
            index=str(index or '?')
        )

import pype
import re
from collections import defaultdict
import numpy as np

def build_brown_tree(path):
    unigram_counts = pype.ngrams( 1, normalizeSigns=False, excludeHeader=False, excludeNumeric=False, excludeCorrections=True )

    brown_file = open( path )
    brown_clusters = brown_file.read()
    brown_file.close()

    brown_clusters = brown_clusters.upper().split("\n")[:-1]
    brown_clusters = [line.split("\t") for line in brown_clusters][1:]
    leaf_addrs = set(addr for addr,label in brown_clusters)

    labels_to_keep = [label for addr,label in brown_clusters if (label,) in unigram_counts and unigram_counts[(label,)] > 50 and not label.startswith("N")]

    def readtree(rootlabel = ''):
        node_text = defaultdict(str)
        # Stores node labels in nodetext dictionary.
        for addr,label in brown_clusters:
            if addr == rootlabel:
                if label in labels_to_keep:
                    node_text[rootlabel] += '\n' + label.upper()
        # Stop recursion once we reach the deepest cluster
        if len(rootlabel) < len(max(leaf_addrs,key=lambda x:len(x))):
            lchild = rootlabel+'0'
            node_text.update( readtree(lchild) )
            rchild = rootlabel+'1'
            node_text.update( readtree(rchild) )
        return node_text

    node_text = readtree()

    def make_binary_tree(depth):
        if depth == 1:
            return []
        else:
            return [make_binary_tree( depth - 1 ), make_binary_tree( depth - 1 )]

    height = len(max(leaf_addrs,key=lambda x:len(x))) + 1
    brown_tree = make_binary_tree(height)

    def get_txt(addr,t):
        if addr == '':
            return t
        else:
            return get_txt(addr[1:],t[0] if addr[0] == '0' else t[1])

    def set_txt(addr,txt,t):
        if addr == '':
            return txt
        else:
            if addr[0] == '0':
                return [set_txt(addr[1:],txt,t[0]), t[1]]
            else:
                return [t[0], set_txt(addr[1:],txt,t[1])]

    for addr in node_text:
        brown_tree = set_txt(addr, addr+'|||'+node_text[addr], brown_tree)

    def clean(t):
        if not isinstance(t,list):
            if '|||' in t:
                t=t.split('|||')[1]
                return t.split('\n')[1:]
            else:
                return t
        elif len(t) == 1:
            return t[0]
        if t[0] != [] and t[1] != []:
            return [clean(t[0]),clean(t[1])]
        elif t[0] == [] and t[1] == []:
            return []
        elif t[1] == []:
            return [clean(t[0])]
        elif t[0] == []:
            return [clean(t[1])]

    # Prune empty subtrees
    orig = brown_tree
    brown_tree=clean(brown_tree)
    while brown_tree != orig:
        orig = brown_tree
        brown_tree=clean(brown_tree)

    return brown_tree, labels_to_keep

def enum_subtrees(tree):
    subtrees = [tree]
    if not isinstance(tree, list):
        return subtrees
    for daughter in tree:
        for subtree in enum_subtrees(daughter):
            if isinstance(subtree,list):
                subtrees.append(subtree)
    return subtrees

def load_brown_model( model_path ):

    # Load brown cluster as a nested list:
    brown_tree, labels = build_brown_tree(model_path)
    padded_labels_brown = [ "                %s" % (''.join(labels[i]),) for i in range(len(labels)) ]

    # Convert tree structure to linkage for displaying
    # as a dendrogram:
    sign2cluster = {sign:i for i,sign in enumerate(labels)}
    
    C_DIST = 0.1
    subtrees = list(reversed(enum_subtrees(brown_tree)))
    synthetic_clusters = []
    distances = []
    counts = []
    n = len(labels)
    clusters_brown = []
    for subtree in subtrees:
        l, r = subtree[0], subtree[1]
        if (not isinstance(l,list)) and (not isinstance(r,list)):
            link = [sign2cluster[l],sign2cluster[r],C_DIST,2]
            synthetic_clusters.append( subtree )
            distances.append(C_DIST)
            counts.append(2)
        elif isinstance(l,list) and (not isinstance(r,list)):
            index = synthetic_clusters.index(l)
            dist = distances[index]+C_DIST
            count = counts[index]+1
            link = [ index + n , sign2cluster[r],dist,count]
            synthetic_clusters.append( subtree )
            distances.append(dist)
            counts.append(count)
        elif (not isinstance(l,list)) and isinstance(r,list):
            index = synthetic_clusters.index(r)
            dist = distances[index]+C_DIST
            count = counts[index]+1
            link = [ sign2cluster[l], index + n , dist, count]
            synthetic_clusters.append( subtree )
            distances.append(dist)
            counts.append(count)
        elif isinstance(l,list) and isinstance(r,list):
            index = synthetic_clusters.index(l)
            dist = distances[index]
            count = counts[index]

            index_ = synthetic_clusters.index(r)
            dist_ = distances[index_]
            count_ = counts[index_]

            link = [ index + n , index_ + n, max(dist,dist_) + C_DIST ,count+count_]
            synthetic_clusters.append( subtree )
            distances.append(max(dist,dist_) + C_DIST)
            counts.append(count+count_)
        clusters_brown.append(link)
    return clusters_brown, padded_labels_brown

def get_contexts( threshold = 50, excludeHeader = False, useFullContext = True, normalizeSigns = False ):
    """
    Constructs a context vector for each sign based on the number of times each other sign
    appears as that sign's neighbor.
    """
    
    unk_tokens = ['X', '[...]', '...']
    control_characters = [("<S>",),("<\S>",),('<UNK>',)]
    transliteration_annotations_regex = r"\?|#|\[|\]"
    
    def get_last_sign( lines, lineNo ):
        """
        Helper function to get the final sign in an entry.
        """
        if lineNo < 0:
            return "<S>"

        else:
            entry, number = lines[lineNo]
            
            if number is not None and number.strip() != "":
                last_sign = pype.format_numeric_sign( number.split()[-1] )
            else:
                last_sign = entry.split()[-1]
            last_sign = last_sign.upper()
                
            if last_sign in unk_tokens \
            or last_sign.startswith("<") \
            or last_sign.endswith(">") \
            or last_sign.endswith("!"):
                return "<UNK>"
            
            last_sign = re.sub( transliteration_annotations_regex, "", last_sign ) 
            return last_sign

    def get_next_sign( lines, lineNo ):
        """
        Helper function to get the next sign after the end of an entry.
        """
        # Check if the current entry has a numeric component or not:
        _, number = lines[lineNo]
        if number is not None and number.strip() != "":
            next_sign = pype.format_numeric_sign( number.split()[0] )
        
        else:
            if lineNo + 1 < len(lines):
                entry, number = lines[lineNo + 1]
                if entry is not None and entry.strip() != "":
                    next_sign = entry.split()[0]
                else:
                    next_sign = pype.format_numeric_sign( number.split()[0] )
            else:
                return "<\S>"
        next_sign = next_sign.upper()
            
        if next_sign in unk_tokens \
        or next_sign.startswith("<") \
        or next_sign.endswith(">") \
        or next_sign.endswith("!"):
            return "<UNK>"

        next_sign = re.sub( transliteration_annotations_regex, "", next_sign ) 
        return next_sign
    
    # Get a list of all of the signs in the signary.
    # Include headers and numeric signs, because they
    # might show up in the context even if they aren't
    # among the signs we're interested in clustering:
    sign_list = [sign for sign in pype.ngrams( 1, normalizeSigns=normalizeSigns, excludeHeader=False, excludeNumeric=False, excludeCorrections=True )]
    sign_list.sort()
    sign_list += control_characters
    sign2i = {sign:i for i,sign in enumerate(sign_list)}
    
    # Context vector: for each non-control character, count 
    # how many times each other sign (including control 
    # characters) appears to the left or right:
    left_contexts    = [ [0 for i in range(len(sign_list))] 
                            for i in range(len(sign_list) - len(control_characters)) ]
    right_contexts   = [ [0 for i in range(len(sign_list))] 
                            for i in range(len(sign_list) - len(control_characters)) ]

    num_observations = [0 for i in range(len(sign_list) - len(control_characters))]

    for j,tablet in enumerate(pype.tablets):
        # Include numeric signs in the context but not the clustering:
        lines = list(tablet.getLines( excludeHeader, excludeNumeric = False ))
        
        for i,(entry,numbers) in enumerate(lines):

            if entry is None:
                continue

            else:
                entry = entry.upper().split()
                # Remove annotations so that eg [M288] is not counted as a different sign from M288.
                entry = [ re.sub( transliteration_annotations_regex, "", sign ) for sign in entry ]
                # Remove modern corrections:
                entry = [ sign for sign in entry if ( not sign.startswith("<") or not sign.endswith(">") ) and not sign.endswith("!") ]
                # Include the last sign from the previous line and first sign from the next line
                entry = [get_last_sign(lines, i-1)] + entry + [get_next_sign(lines, i)]
                entry = tuple( entry )
                # Collapse sign variants
                if normalizeSigns:
                    entry = tuple( pype.normalize( sign ) for sign in entry )

                for index in range( 1, len(entry) - 1 ):
                    sign = entry[index]
                    sign = re.sub( transliteration_annotations_regex, "", sign )
                    sign = pype.format_numeric_sign(sign)

                    if sign in unk_tokens or sign.startswith('N'):
                        continue

                    num_observations[sign2i[(sign,)]] += 1

                    left = entry[index - 1]
                    left = re.sub( transliteration_annotations_regex, "", left )
                    if left in unk_tokens:
                        left = '<UNK>'
                    left_contexts[ sign2i[(sign,)] ][ sign2i[(left,)] ] += 1
                    
                    right = entry[index + 1]
                    right = re.sub( transliteration_annotations_regex, "", right )
                    if right in unk_tokens:
                        right = '<UNK>'
                    right_contexts[ sign2i[(sign,)] ][ sign2i[(right,)] ] += 1

    # Concatenate partial contexts into a full context vector for each sign:
    contexts = []
    for i,sign in enumerate( sign_list[:-len(control_characters)] ):
        context = left_contexts[i] + right_contexts[i]
        contexts.append(context)
    
    # Prune out infrequent signs to make the diagram smaller
    # and easier to interpret:
    pruned_contexts = []
    pruned_sign_list = []
    for i,(sign,) in enumerate( sign_list[:-len(control_characters)] ):
        if num_observations[i] >= threshold and '+' not in sign and not sign.startswith('N'):
            pruned_contexts.append( contexts[i] )
            pruned_sign_list.append( (sign,) )
    
    return pruned_sign_list, np.asarray(pruned_contexts)

