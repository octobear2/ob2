class Photocrop
    constructor: (container, finished_callback=null) ->
        @container = $(container)
        if finished_callback != null
            @finished_callback = finished_callback

    load: (image, max_size=256) ->
        @image = image
        @canvas = document.createElement "canvas"
        @container.empty()
        @container.append @canvas
        if @image.width == 0 or @image.height == 0
            throw "Image has no pixels in it."
        width_to_height = @image.width / @image.height
        if @image.width > @image.height
            @canvas_width = Math.min @image.width, max_size
            @canvas_height = @canvas_width / width_to_height
        else
            @canvas_height = Math.min @image.height, max_size
            @canvas_width = @canvas_height * width_to_height
        @canvas.width = @canvas_width
        @canvas.height = @canvas_height
        @context = @canvas.getContext "2d"
        @context.drawImage @image, 0, 0, @canvas_width, @canvas_height
        @canvas.addEventListener "mousedown", @mousedown
        @canvas.addEventListener "mouseup", @mouseup
        @canvas.addEventListener "mouseleave", @mouseup
        @canvas.addEventListener "mousemove", @mousemove
        @param_size = Math.min @canvas_width, @canvas_height
        @param_topleft = [(@canvas_width - @param_size) / 2,
                          (@canvas_height - @param_size) / 2]
        @drawCropSquare @param_topleft[0], @param_topleft[1], @param_size
        @finished_callback()

    clear: ->
        @container.empty()

    drawCropSquare: (x, y, size) ->
        @context.drawImage @image, 0, 0, @canvas_width, @canvas_height
        @context.lineWidth = 2.0
        @context.fillStyle = "rgba(64, 64, 64, 0.85)"

        keypoints = [[0, 0], [x + size, 0], [@canvas_width - 1, 0],
                     [0, y], [x, y], [x + size, y],
                     [x, y + size], [x + size, y + size], [@canvas_width - 1, y + size],
                     [0, @canvas_height - 1], [x, @canvas_height - 1], [@canvas_width - 1, @canvas_height - 1]]

        @context.beginPath()
        @context.moveTo(keypoints[4]...)
        @context.lineTo(keypoints[5]...)
        @context.lineTo(keypoints[7]...)
        @context.lineTo(keypoints[6]...)
        @context.closePath()
        @context.stroke()

        for path in [[0, 1, 5, 3],
                     [1, 2, 8, 7],
                     [8, 11, 10, 6],
                     [10, 9, 3, 4]]
            @context.beginPath()
            @context.moveTo(keypoints[path[0]]...)
            @context.lineTo(keypoints[path[1]]...)
            @context.lineTo(keypoints[path[2]]...)
            @context.lineTo(keypoints[path[3]]...)
            @context.closePath()
            @context.fill()

    mousedown: (event) =>
        if event.which == 1
            @param_start = [event.offsetX, event.offsetY]

    mouseup: (event) =>
        @finished_callback()

    mousemove: (event) =>
        if event.which == 1
            rectangle_width = Math.abs(event.offsetX - @param_start[0])
            rectangle_height = Math.abs(event.offsetY - @param_start[1])
            @param_size = Math.max(rectangle_width, rectangle_height) + 1
            if event.offsetX < @param_start[0]
                if event.offsetY < @param_start[1]
                    @param_size = Math.min @param_start[0], @param_start[1], @param_size
                    @param_topleft = [@param_start[0] - @param_size, @param_start[1] - @param_size]
                else
                    @param_size = Math.min @param_start[0], @canvas_height - @param_start[1], @param_size
                    @param_topleft = [@param_start[0] - @param_size, @param_start[1]]
            else
                if event.offsetY < @param_start[1]
                    @param_size = Math.min @canvas_width - @param_start[0], @param_start[1], @param_size
                    @param_topleft = [@param_start[0], @param_start[1] - @param_size]
                else
                    @param_size = Math.min @canvas_width - @param_start[0], @canvas_height - @param_start[1], @param_size
                    @param_topleft = [@param_start[0], @param_start[1]]
            @drawCropSquare @param_topleft[0], @param_topleft[1], @param_size

    toDataURL: (size=256) ->
        target_canvas = document.createElement "canvas"
        image_to_canvas_w = @image.width / @canvas_width
        image_to_canvas_h = @image.height / @canvas_height
        image_topleft = [@param_topleft[0] * image_to_canvas_w,
                         @param_topleft[1] * image_to_canvas_h]
        image_size = [@param_size * image_to_canvas_w,
                      @param_size * image_to_canvas_h]
        target_canvas.width = size
        target_canvas.height = size
        target_context = target_canvas.getContext "2d"
        target_context.drawImage @image, image_topleft[0], image_topleft[1], image_size[0], image_size[1], 0, 0, size, size
        return target_canvas.toDataURL("image/jpeg", 0.85)


window.Photocrop = Photocrop
