$(document).ready ->
    fileinput = $(".js-photocrop-fileinput")
    cropper = $(".js-photocrop-cropper")
    submit = $(".js-photocrop-submit")
    cancel = $(".js-photocrop-cancel")
    fileoutput = $(".js-photocrop-output")
    photocrop = null
    fileinput.change ->
        photocrop = new Photocrop cropper, ( ->
            fileoutput.val photocrop.toDataURL()
        )
        image = new Image()
        image.onload = ->
            photocrop.load image
        file = fileinput.prop("files")[0]
        filereader = new FileReader()
        filereader.onload = ->
            image.src = filereader.result
        filereader.readAsDataURL file
        fileinput.parent().hide()
        cropper.show()
        submit.show()

    cancel.click ->
        fileinput.wrap("<form>").parent("form").trigger("reset")
        fileinput.unwrap()
        fileinput.parent().show()
        if photocrop != null
            photocrop.clear()
        cropper.hide()
        submit.hide()
        fileinput.click()
