#! /usr/bin/perl

# clear?
# modify refresh time for new track

use strict;
use warnings;
use Audio::MPD;
use HTML::Template;
use CGI;
use MIME::Base64;
use POSIX qw(strftime);
use Encode qw(encode decode);
use utf8;

my %cfg=(mpdhost => 'pyromachy',
         host => 'radiant.homenet.firedrake.org',
         port => ':8080',
         script => '/cgi-bin/radio.cgi',
         history => 10,
         musicroot => '/mnt/storage/audio',
           );
my $uri="http://$cfg{host}$cfg{port}$cfg{script}";

my $q=CGI->new;
my %param=map{$_ => scalar $q->param($_)} $q->param;
my %cookie=map{$_ => scalar $q->cookie($_)} $q->cookie;

my $path='';
if (exists $param{path}) { # even if it's null
  $path=$param{path} || '';
} elsif (exists $cookie{'yokusou.path'}) {
  $path=$cookie{'yokusou.path'} || '';
}

if ($path eq '/') {
  $path='';
} else {
  $path=decode_base64($path);
}

while (! -d "$cfg{musicroot}/$path") {
  unless ($path =~ s/\/[^\/]*$//) {
    $path='';
    last;
  }
}

if (exists $param{search}) {
  $path=join(':','','search',$param{type},$param{string});
}

my $ep=eb64($path);

my $r=0;

my $mpd=Audio::MPD->new(host => $cfg{mpdhost});
my %p;

my $coll=$mpd->collection;
my $pl=$mpd->playlist;
if (exists $param{queue}) {
  my @pl=$pl->as_items;
  my $start=scalar @pl;
  my $qp=decode_base64($param{queue});
  if ($qp =~ /\.m3u/) {
    if ($qp =~ /\[r\]/) {
      kill_qf();
      $SIG{CHLD}='IGNORE';
      my $subpid=fork;
      unless ($subpid) {
        open STDOUT, '>/dev/null' or die "Can't open /dev/null: $!";
        open STDIN, '</dev/null' or die "Can't open /dev/null: $!";
        exec('/usr/local/bin/queuefiller',"$cfg{musicroot}/$qp");
      }
      if ($mpd->status->state eq 'stop') {
        while (scalar ($pl->as_items) == $start) {
          sleep 1;
        }
      }
    } else {
      (my $base=$qp) =~ s/\/[^\/]*$//;
      open I,'<',"$cfg{musicroot}/$qp";
      while (<I>) {
        chomp;
        my $r="$base/$_";
        while ($r =~ s/[^\/]+\/\.\.\///) {
        }
        if (my $s=$coll->song($r)) {
          $pl->add(decode('UTF-8',$r));
        }
      }
      close I;
    }
  } else {
    $pl->add(decode('UTF-8',$qp));
  }
  if ($mpd->status->state eq 'stop') {
    $mpd->play($start);
  }
  $r=1;
}

if (exists $param{skip}) {
  if (exists $param{plid}) {
    $pl->delete($param{plid});
  } else {
    $mpd->next;
  }
  $r=1;
}

if (exists $param{move}) {
  if (exists $param{plid} && exists $param{dest}) {
    $pl->move($param{plid},$param{dest});
  }
  $r=1;
}

if (exists $param{crop}) {
  kill_qf();
  $pl->crop;
  $r=1;
}

if (exists $param{update}) {
  if ($path =~ /^:/) {
    $mpd->updatedb();
  } else {
    $mpd->updatedb('"'.$path.'"');
  }
  $r=1;
}

if (exists $param{eqf}) {
  kill_qf();
  $r=1;
}

if (exists $param{pause}) {
  $mpd->pause(1);
  $r=1;
}

if (exists $param{resume}) {
  $mpd->pause(0);
  $r=1;
}

if (defined $mpd->status->updating_db && $mpd->status->updating_db==1) {
  $p{updating}=1;
}

if ($r) {
  print $q->redirect("$uri?path=$ep");
  exit;
}

{
  my $np=-1;
  if ($mpd->status->state ne 'stop') {
    $np=$mpd->status->song;
    if ($mpd->status->state eq 'play') {
      $p{play}=1;
    } else {
      $p{pause}=1;
    }
  }
  my @pl=$pl->as_items;
  if ($np>$cfg{history}) {
    foreach ($cfg{history}..$np) {
      $pl->delete(0);
      $np--;
    }
    @pl=$pl->as_items;
  }
  my $del=0;
  my $status=0;
  if (@pl) {
    foreach my $pi (0..$#pl) {
      my $s=$pl[$pi];
      my $meta=get_meta($s);
      if ($pi == $np) {
        $status=1;
        $meta->{stime}=time-$mpd->status->time->seconds_sofar;
      } elsif ($status==0) {
        $del++;
      }
      $meta->{"status.$status"}=1;
      $meta->{plid}=$pi;
      $meta->{queue}=eb64($s->file);
      push @{$p{list}},$meta;
      if ($pi == $np) {
        $status=2;
      }
    }
    if ($p{play}) {
      foreach my $pix ($np+1..$#pl) {
        $p{list}[$pix]{stime}=$p{list}[$pix-1]{stime}+$p{list}[$pix-1]{len};
      }
      foreach my $pix ($np..$#pl) {
        $p{list}[$pix]{starttime}=strftime('%H:%M',localtime($p{list}[$pix]{stime}));
      }
    }
    foreach my $pix ($np+2..$#pl) {
      $p{list}[$pix]{top}=$np+1;
    }
    foreach my $pix ($np+3..$#pl) {
      $p{list}[$pix]{up}=$pix-1;
    }
    foreach my $pix ($np+1..$#pl-1) {
      $p{list}[$pix]{down}=$pix+1;
    }
  }
}

my %i;
if ($path =~ /^:search:([^:]*):(.*)/) {
  my ($type,$string)=($1,$2);
  my @res;
  if ($type eq 'title') {
    @res=$coll->songs_with_title_partial($string);
  } elsif ($type eq 'artist') {
    @res=$coll->songs_by_artist_partial($string);
  } elsif ($type eq 'album') {
    @res=$coll->songs_from_album_partial($string);
  }
  $i{d}=[];
  $i{p}=[];
  $i{f}=\@res;
  $p{search}=1;
} else {
  my @d=$coll->items_in_dir($path);
  foreach my $item (@d) {
    if (ref $item eq 'Audio::MPD::Common::Item::Directory') {
      push @{$i{d}},$item;
    } elsif (ref $item eq 'Audio::MPD::Common::Item::Playlist') {
      push @{$i{p}},$item;
    } elsif (ref $item eq 'Audio::MPD::Common::Item::Song') {
      push @{$i{f}},$item;
    }
  }
  @{$i{d}}=sort {lc($a->directory) cmp lc($b->directory)} @{$i{d}};
  @{$i{p}}=sort {$a->playlist cmp $b->playlist} @{$i{p}};
  @{$i{f}}=sort {$a->file cmp $b->file} @{$i{f}};
}
{
  my @item;
  if ($path) {
    push @item,{first => 1,path => '',name => 'Root'};
    if ($path =~ /\//) {
      (my $pp=$path) =~ s/\/[^\/]+$//;
      push @item,{path => eb64($pp),name => 'Parent'};
    }
  }
  my $ll='';
  foreach my $dir (@{$i{d}}) {
    (my $dn=$dir->directory) =~ s/.*\///;
    push @item,{path => eb64($dir->directory),
                name => $dn};
    if (uc(substr($dn,0,1)) ne $ll) {
      $ll=uc(substr($dn,0,1));
      $item[-1]{key}=$ll;
      push @{$p{dirheaders}},{key => $ll};
    }
  }
  if (@item) {
    if (exists $p{dirheaders} && scalar @{$p{dirheaders}} < 20) {
      delete $p{dirheaders};
      map {delete $item[$_]{key}} (0..$#item);
    }
    $p{dir}=\@item;
  }
}
{
  my @item;
  if (ref $i{p} eq 'ARRAY') {
    foreach my $pl (sort {lc($a->playlist) cmp lc($b->playlist)} @{$i{p}}) {
      (my $pn=$pl->playlist) =~ s/.*\///;
      $pn =~ s/\.m3u$//;
      push @item,{path => $ep,
                  queue => eb64($pl->playlist),
                  name => $pn};
    }
    if (@item) {
      $p{playlist}=\@item;
    }
  }
}
{
  my @item;
  if ($i{f}) {
    foreach my $f (sort {$a->file cmp $b->file} @{$i{f}}) {
      my $y=get_meta($f);
      my $name=$y->{title};
      my $albumname=($y->{artist} || 'unknown artist').' – '.($y->{album} || 'unknown album');
      my $search=0;
      my $mp='';
      if ($path =~ /^:search:([^:]*):(.*)/) {
        ($mp=$f->file) =~ s/\/[^\/]*$//;
      } else {
        $name=get_meta($f)->{title};
      }
      push @item,{path => $ep,
                  queue => eb64($f->file),
                  name => $name,
                  albumname => $albumname,
                  albumpath => eb64($mp),
                };
    }
  }
  if (@item) {
    $p{track}=\@item;
  }
}
$p{uri}=$uri;
$p{path}=$path;
$p{ep}=$ep;
$p{qf}=read_qf();
my $ref=60;
if ($mpd->status->state eq 'play') {
  my $r=$mpd->status->time->seconds_left;
  if ($r<$ref) {
    $ref=$r;
  }
}

my $tmpl=HTML::Template->new(arrayref => [<DATA>],
                             die_on_bad_params => 0,
                             global_vars => 1);
$tmpl->param(%p);

my $cookie=CGI->cookie(-name => 'yokusou.path',
                       -value => $ep  ,
                       -expires => '+2d',
                       -path => $cfg{script},
                       -domain => $cfg{host},
                       );
binmode(STDOUT, ":utf8");
print $q->header(-cookie => $cookie,
                 -expires => 'now',
                 -charset => 'UTF-8',
                 -refresh => "$ref;URL=$uri");

print $tmpl->output;

sub eb64 {
  my $in=shift;
  my $out=encode_base64(encode('UTF-8',$in));
  $out =~ s/\s+//g;
  return $out;
}

sub get_meta {
  my $f=shift;
  my %o;
  {
    my @y=split '/',$f->file;
    $o{title}=pop @y;
    $o{title} =~ s/^\d+[-. _]*//;
    $o{title} =~ s/\.[a-z\d]+$//;
    $o{album}='';
    if ($y[0] eq 'Classical') {
      $o{artist}=$y[1] || '';
      $o{album}=$y[3] || '';
    } elsif ($y[0] eq 'Popular') {
      $o{artist}=$y[1] || '';
      $o{album}=$y[2] || '';
    } elsif ($y[0] eq 'Soundtrack') {
      $o{artist}=$y[2] || '';
      $o{album}=$y[3] || '';
    }
    $o{album} =~ s/^\d+[- _]*//;
  }
  $o{title}=$f->title || $o{title};
  $o{artist}=$f->artist || $o{artist};
  $o{album}=$f->album || $o{album};
  {
    $o{len}=$f->time || 0;
    my $mm=int($o{len}/60);
    my $ss=$o{len} % 60;
    $o{length}=sprintf('%04d:%02d',$mm,$ss);
    $o{length} =~ s/^0+//;
    $o{length} =~ s/^:/0:/;
  }
  $o{id}=$f->id;
  return \%o;
}

sub kill_qf {
  open I,'-|',qw(ps --no-header -o pid -C queuefiller);
  while (<I>) {
    chomp;
    kill 15,$_;
  }
  close I;
}

sub read_qf {
  my $out='';
  open I,'-|',qw(ps --no-header -o args -wwC queuefiller);
  while (<I>) {
    chomp;
    s/.*$cfg{musicroot}\///;
    $out=$_;
    last;
  }
  close I;
  return $out;
}

__DATA__
<html>
<head><title>Radio Firedrake</title>
<link rel="icon" type="image/png" href="/icon/radio.png" />
</head>
<body>

<table><tr>
<tmpl_if name=play>
<td><a href="http://pyromachy.homenet.firedrake.org:8000/stream">stream</a></td>
<td><a href="<tmpl_var name=uri>?crop=1">clear</a></td>
<tmpl_if name=qf>
<td><a href="<tmpl_var name=uri>?eqf=1">cancel <tmpl_var name=qf escape=html></a></td>
</tmpl_if>
<td><a href="<tmpl_var name=uri>?pause=1">pause</a></td>
</tmpl_if>
<tmpl_if name=pause>
<td><a href="<tmpl_var name=uri>?resume=1">resume</a></td>
</tmpl_if>
<tmpl_unless name="updating">
<td><a href="<tmpl_var name=uri>?update=1">update db</a></td>
</tmpl_unless>
<td>
<form action="<tmpl_var name=uri>" method=post>
<select name=type>
<option value=title>Title</option>
<option value=artist>Artist</option>
<option value=album>Album</option>
</select>
<input type=text name=string>
<input type=submit name=search value=Search>
</form>
</td>
</tr></table>
<hr>

<tmpl_if name=list>
<table>
<tmpl_loop name=list>
<tr<tmpl_if name=status.1> bgcolor=#d0d0d0</tmpl_if>>
<td valign=top><tmpl_var name=title escape=html><tmpl_unless name=status.0><br>
<b><tmpl_var name=artist escape=html></b><br>
<i><tmpl_var name=album escape=html></i></tmpl_unless></td>
<td valign=top><tmpl_unless name=status.0><tmpl_var name=starttime escape=html><br></tmpl_unless>
<tmpl_var name=length escape=html></td>
<td><a href="<tmpl_var name=uri>?queue=<tmpl_var name=queue escape=html>">Requeue</a></td>
<tmpl_if name=status.1>
<td><a href="<tmpl_var name=uri>?skip=1">Skip</a></td>
</tmpl_if>
<tmpl_if name=status.2>
<td>
<a href="<tmpl_var name=uri>?skip=1&plid=<tmpl_var name=plid>">Skip</a>
</td>
<tmpl_if name=top>
<td>
<a href="<tmpl_var name=uri>?move=1&plid=<tmpl_var name=plid>&dest=<tmpl_var name=top>">Next</a>
</td>
</tmpl_if>
<tmpl_if name=up>
<td>
<a href="<tmpl_var name=uri>?move=1&plid=<tmpl_var name=plid>&dest=<tmpl_var name=up>">Up</a>
</td>
</tmpl_if>
<tmpl_if name=down>
<td>
<a href="<tmpl_var name=uri>?move=1&plid=<tmpl_var name=plid>&dest=<tmpl_var name=down>">Down</a>
</td>
</tmpl_if>
</tmpl_if>
</tr>
</tmpl_loop>
</table>
<hr>
</tmpl_if>

<tmpl_if name=playlist>
<tmpl_loop name=playlist>
<a href="<tmpl_var name=uri>?queue=<tmpl_var name=queue escape=html>"><tmpl_var name=name escape=html></a><br>
</tmpl_loop>
<hr>
</tmpl_if>

<tmpl_if name=track>
<tmpl_if name=search><ul><tmpl_else><ol></tmpl_if>
<tmpl_loop name=track>
<li><a href="<tmpl_var name=uri>?queue=<tmpl_var name=queue escape=html>"><tmpl_var name=name escape=html></a><tmpl_if name=albumpath> [<a href="<tmpl_var name=uri>?path=<tmpl_var name=albumpath escape=html>"><tmpl_var name=albumname escape=html></a>]</tmpl_if></li>
</tmpl_loop>
<tmpl_if name=search></ul><tmpl_else></ol></tmpl_if>
<hr>
</tmpl_if>

<tmpl_if name=dir>
<tmpl_if name=dirheaders>
<tmpl_loop name=dirheaders>
<a href="#<tmpl_var name=key escape=html>"><tmpl_var name=key escape=html></a>
</tmpl_loop>
</tmpl_if>
<tmpl_loop name=dir>
<tmpl_if name=key>
<h2><a name="<tmpl_var name=key escape=html>"><tmpl_var name=key escape=html></a></h2>
</tmpl_if>
<a href="<tmpl_var name=uri>?path=<tmpl_var name=path escape=html>"><tmpl_var name=name escape=html></a><br>
</tmpl_loop>
<hr>
</tmpl_if>

</body></html>
