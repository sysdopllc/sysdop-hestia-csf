#!/usr/bin/perl
sub custom_line
{
	my $line = shift;
	my $lgfile = shift;

	# Existing tenant-specific rule must survive the Hestia overlay.
	if ($line =~ /never-match-fixture/) {
		return ("fixture", "192.0.2.1", "fixture", "5", "443", "1", "0");
	}

	return 0;
}

1;
