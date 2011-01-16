# -*- coding: ascii -*-
#
#  Util/asn1.py : Minimal support for ASN.1 DER binary encoding.
#
# ===================================================================
# The contents of this file are dedicated to the public domain.  To
# the extent that dedication to the public domain is not available,
# everyone is granted a worldwide, perpetual, royalty-free,
# non-exclusive license to exercise all rights associated with the
# contents of this file for any purpose whatsoever.
# No rights are reserved.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# ===================================================================

from Crypto.Util.number import long_to_bytes, bytes_to_long

__all__ = [ 'DerObject', 'DerInteger', 'DerSequence' ]

class DerObject:
        """Base class for defining a single DER object.
        
        Instantiate this class ONLY when you have to decode a DER element.
        """

        # Known TAG types
        typeTags = { 'SEQUENCE':'\x30', 'BIT STRING':'\x03', 'INTEGER':'\x02' }

        def __init__(self, ASN1Type=None):
                """Initialize the DER object according to a specific type.

                The ASN.1 type is either specified as the ASN.1 string (e.g.
                'SEQUENCE'), directly with its numerical tag or with no tag
                atl all (None)."""
                self.typeTag = self.typeTags.get(ASN1Type, ASN1Type)
                self.payload = ''

        def _lengthOctets(self, payloadLen):
                """Return a string that encodes the given payload length (in
                bytes) in a format suitable for a DER length tag (L).
                """
                if payloadLen>127:
                        encoding = long_to_bytes(payloadLen)
                        return chr(len(encoding)+128) + encoding
                return chr(payloadLen)

        def encode(self):
                """Return a complete DER element, fully encoded as a TLV."""
                return self.typeTag + self._lengthOctets(len(self.payload)) + self.payload      

        def _decodeLen(self, idx, str):
                """Given a (part of a) DER element, and an index to the first byte of
                a DER length tag (L), return a tuple with the payload size,
                and the index of the first byte of the such payload (V).
                
                Raises a ValueError exception if the DER length is invalid.
                Raises an IndexError exception if the DER element is too short.
                """
                length = ord(str[idx])
                if length<=127:
                        return (length,idx+1)
                payloadLength = bytes_to_long(str[idx+1:idx+1+(length & 0x7F)])
                if payloadLength<=127:
                        raise ValueError("Not a DER length tag.")
                return (payloadLength, idx+1+(length & 0x7F))

        def decode(self, derEle, noLeftOvers=0):
                """Decode a complete DER element, and re-initializes this
                object with it.
                
                @param derEle       A complete DER element. It must start with a DER T
                                    tag.
                @param noLeftOvers  Indicate whether it is acceptable to complete the
                                    parsing of the DER element and find that not all
                                    bytes in derEle have been used.
                @return             Index of the first unused byte in the given DER element.

                Raises a ValueError exception in case of parsing errors.
                Raises an IndexError exception if the DER element is too short.
                """
                try:
                        self.typeTag = derEle[0]
                        if (ord(self.typeTag) & 0x1F)==0x1F:
                                raise ValueError("Unsupported DER tag")
                        (length,idx) = self._decodeLen(1, derEle)
                        if noLeftOvers and len(derEle) != (idx+length):
                                raise ValueError("Not a DER structure")
                        self.payload = derEle[idx:idx+length]
                except IndexError:
                        raise ValueError("Not a valid DER SEQUENCE.")
                return idx+length

class DerInteger(DerObject):
        def __init__(self, value = 0):
                """Class to model an INTEGER DER element.
            
                Limitation: only non-negative values are supported.
                """
                DerObject.__init__(self, 'INTEGER')
                self.value = value

        def encode(self):
                """Return a complete INTEGER DER element, fully encoded as a TLV."""
                self.payload = long_to_bytes(self.value)
                if ord(self.payload[0])>127:
                        self.payload = '\x00' + self.payload
                return DerObject.encode(self)

        def decode(self, derEle, noLeftOvers=0):
                """Decode a complete INTEGER DER element, and re-initializes this
                object with it.
            
                @param derEle       A complete INTEGER DER element. It must start with a DER
                                    INTEGER tag.
                @param noLeftOvers  Indicate whether it is acceptable to complete the
                                    parsing of the DER element and find that not all
                                    bytes in derEle have been used.
                @return             Index of the first unused byte in the given DER element.
                
                Raises a ValueError exception if the DER element is not a
                valid non-negative INTEGER.
                Raises an IndexError exception if the DER element is too short.
                """
                tlvLength = DerObject.decode(self, derEle, noLeftOvers)
                if self.typeTag!=self.typeTags['INTEGER']:
                        raise ValueError ("Not a DER INTEGER.")
                if ord(self.payload[0])>127:
                        raise ValueError ("Negative INTEGER.")
                self.value = bytes_to_long(self.payload)
                return tlvLength
                                
class DerSequence(DerObject):
        """Class to model a SEQUENCE DER element.
        
        This object behave like a dynamic Python sequence.
        Sub-elements that are INTEGERs, look like Python integers.
        Any other sub-element is a binary string encoded as the complete DER
        sub-element (TLV).
        """

        def __init__(self):
                """Initialize the SEQUENCE DER object. Always empty
                initially."""
                DerObject.__init__(self, 'SEQUENCE')
                self._seq = []

        ## A few methods to make it behave like a python sequence

        def __delitem__(self, n):
                del self._seq[n]
        def __getitem__(self, n):
                return self._seq[n]
        def __setitem__(self, key, value):
                self._seq[key] = value  
        def __setslice__(self,i,j,sequence):
                self._seq[i:j] = sequence
        def __delslice__(self,i,j):
                del self._seq[i:j]
        def __getslice__(self, i, j):
                return self._seq[max(0, i):max(0, j)]
        def __len__(self):
                return len(self._seq)
        def append(self, item):
                return self._seq.append(item)

        def hasOnlyInts(self):
                """Return 1/True is all items in this sequence are numbers."""
                if not self._seq: return 0
                test = 0
                for item in self._seq:
                        try:
                                test += item
                        except TypeError:
                                return 0
                return 1

        def encode(self):
                """Return the DER encoding for the ASN.1 SEQUENCE, containing
                the non-negative integers and longs added to this object.

                Limitation: Raises a ValueError exception if it some elements
                in the sequence are neither Python integers nor complete DER INTEGERs.
                """
                self.payload = ''
                for item in self._seq:
                        try:
                                self.payload += item
                        except:
                                try:
                                        self.payload += DerInteger(item).encode()
                                except:
                                        raise ValueError("Trying to DER encode an unknown object")
                return DerObject.encode(self)

        def decode(self, derEle, noLeftOvers=0):
                """Decode a complete SEQUENCE DER element, and re-initializes this
                object with it.
             
                @param derEle       A complete SEQUENCE DER element. It must start with a DER
                                    SEQUENCE tag.
                @param noLeftOvers  Indicate whether it is acceptable to complete the
                                    parsing of the DER element and find that not all
                                    bytes in derEle have been used.
                @return             Index of the first unused byte in the given DER element.
        
                DER INTEGERs are decoded into Python integers. Any other DER
                element is not decoded. Its validity is not checked.
            
                Raises a ValueError exception if the DER element is not a
                valid DER SEQUENCE.
                Raises an IndexError exception if the DER element is too short.
                """

                self._seq = []
                try:
                        tlvLength = DerObject.decode(self, derEle, noLeftOvers)
                        if self.typeTag!=self.typeTags['SEQUENCE']:
                                raise ValueError("Not a DER SEQUENCE.")
                        # Scan one TLV at once
                        idx = 0
                        while idx<len(self.payload):
                                typeTag = self.payload[idx]
                                if typeTag==self.typeTags['INTEGER']:
                                        newInteger = DerInteger()
                                        idx += newInteger.decode(self.payload[idx:])
                                        self._seq.append(newInteger.value)
                                else:
                                        itemLen,itemIdx = self._decodeLen(idx+1,self.payload)
                                        self._seq.append(self.payload[idx:itemIdx+itemLen])
                                        idx = itemIdx + itemLen
                except IndexError:
                        raise ValueError("Not a valid DER SEQUENCE.")
                return tlvLength

