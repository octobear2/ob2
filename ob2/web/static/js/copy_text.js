$(document).ready(function() {
    $('.js-copy-btn').each(function () {
        var $copyText = $('.js-copytxt[for="' + this.id + '"]');
        var $tooltip = $('.mdl-tooltip[for="' + this.id + '"]');
        $(this).click(function () {
            $copyText.select();

            var success = false;
            try {
                success = document.execCommand('copy');
            } catch (err) { /* Ignore */ }
            if (!success) {
                alert("Your browser doesn't support copying to clipboard!");
            } else {
                if ($tooltip.length > 0) {
                    var orig = $tooltip.text();
                    $tooltip.text("Copied!");
                    setTimeout(function () {
                        $tooltip.text(orig);
                    }, 1000);
                }
            }
        });
    });
});
