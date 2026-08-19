<?php
$TAB = "CSF";

include $_SERVER["DOCUMENT_ROOT"] . "/inc/main.php";

// Hestia's root account is renameable. Authorize by effective role and never
// expose the privileged firewall UI while impersonating another account.
// Portable across Hestia versions: newer builds expose the role in "role",
// older ones (<=1.8.x) only in "userContext". Honour either.
if (($_SESSION["userContext"] ?? $_SESSION["role"] ?? "") !== "admin" || !empty($_SESSION["look"])) {
	header("Location: /list/user/");
	exit();
}

render_page($_SESSION["user"], $TAB, "list_csf");

$_SESSION["back"] = $_SERVER["REQUEST_URI"];
