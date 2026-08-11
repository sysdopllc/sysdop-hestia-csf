#!/usr/bin/perl
sub custom_line
{
	my $line = shift;
	my $lgfile = shift;

	# HestiaCP failed panel authentication:
	# YYYY-MM-DD HH:MM:SS username address failed to login
	if (
		($globlogs{CUSTOM1_LOG}{$lgfile}) and
		($line =~ /^\S+\s+\S+\s+(\S+)\s+([0-9A-Fa-f:.]+)\s+failed to login\s*$/)
	) {
		my $account = $1;
		my $ip = $2;
		$ip =~ s/^::ffff://;
		return (
			"Failed HestiaCP login from",
			"$ip|$account",
			"hestia",
			"5",
			"56464",
			"1",
			"0",
		);
	}

	return 0;
}

1;
