<main class="app-content">
	<div class="l-separator"></div>
	<div class="l-center units">
		<iframe scrolling="auto" name="myiframe" id="myiframe" src="/list/csf/frame.php" frameborder="0" width="100%" onload="resizeIframe(this);"></iframe>
	</div>
</main>

<script>
function resizeIframe(obj) {
	obj.style.height = obj.contentWindow.document.body.scrollHeight + 'px';
	window.scrollTo(0, 0);
}
</script>
