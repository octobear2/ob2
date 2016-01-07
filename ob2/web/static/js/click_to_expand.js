$(document).ready(function() {
    $(".js-click-to-expand").each(function(_, element) {
        var orphans = $(element).find("tbody").children().slice(7);
        if (orphans.length < 4) {
            return;
        }
        var element_wrapper = $("<div></div>")
            .css({"position": "relative",
                  "margin-bottom": "32px"});
        $(element).wrap(element_wrapper);
        element_wrapper = $(element).parent();
        orphans.hide();
        var expander = $("<div></div>")
            .css({"height": "32px",
                  "width": "100%",
                  "line-height": "32px",
                  "text-align": "center",
                  "font-size": "14px",
                  "position": "absolute",
                  "top": "100%",
                  "left": "0",
                  "z-index": "1000",
                  "border-radius": "0",
                  "box-sizing": "border-box"})
            .addClass("mdl-button mdl-js-button mdl-color--blue-grey-800 mdl-color-text--white")
            .text("Click to expand")
            .click(function(event) {
                $(this).remove();
                orphans.show();
                element_wrapper.css({"margin-bottom": "0"});
            });
        $(element_wrapper).append(expander);
    });
});
