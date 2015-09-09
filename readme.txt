=Introduction

Yokosou is a lightweight web-based control interface to MPD
<http://www.musicpd.org/>.

There are lots of web interfaces. Why did I write another? Because
most of them are in PHP, or require horribly complex server
configuration and add-ons, and/or complex modern browsers.

=Copyright

Yokosou is Copyright 2015 Roger Bell_West.

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 3 of the License, or (at your
option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
Public License for more details.

You should have received a copy of the GNU General Public License along
with this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.

=Prerequisites

This program should work with any reasonably modern Perl.

It relies on these non-core modules:

Audio::MPD
HTML::Template
MIME::Base64

You will need to configure radio.cgi: most information is in the %cfg
hash at the start of the code.

mpdhost -> the address of the MPD server
host -> the address of the web server on which the script is running
port -> if needed, a colon and the port number of the web server
script -> the path to the script on the web server
history -> the number of played tracks to show
musicroot -> the path to the music repository

You will also need to configure the path to the MPD audio stream, in
the HTML template section (under the __DATA__ marker), and the path to
queuefiller (which needs to be run by the web user).

=Use

Access the script through any web browser (I've deliberately kept it
simple and javascript-free; one of my test platforms is the
experimental browser on the Kobo). This does not need to be the
machine that's playing the strem.

A playlist file containing "[r]" will be shuffled indefinitely.
(That's the only case that requires the queuefiller.)

=Bugs

A random playlist does not start unless a track is already being
played.
