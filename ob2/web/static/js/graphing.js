$(document).ready(function() {
    function draw_histogram(graph_html, data) {
        var minX = Math.min(0, d3.min(data, function(d) { return d.x; }));
        var maxX = d3.max(data, function(d) { return d.dx; });
        var minY = Math.min(0, d3.min(data, function(d) { return d.y; }));
        var maxY = d3.max(data, function(d) { return d.y; });
        var graph = $(graph_html);
        var graphWidth = graph.width();
        var graphHeight = graphWidth / parseFloat(graph.data("aspectratio"));
        var margin = {top: 20, right: 10, bottom: 30, left: 30};
        var innerWidth = graphWidth - margin.left - margin.right;
        var innerHeight = graphHeight - margin.top - margin.bottom;
        var xScale = d3.scale.linear()
            .domain([minX, maxX])
            .range([0, innerWidth]);
        var yScale = d3.scale.linear()
            .domain([minY, maxY])
            .range([innerHeight, 0]);
        var xAxisTicks = data
            .map(function(d) { return d.x; })
            .concat([data[data.length - 1].dx]);
        xAxisTicks = xAxisTicks.filter(function(item, pos) {
            return xAxisTicks.indexOf(item) == pos;
        });
        var xAxis = d3.svg.axis()
            .scale(xScale)
            .tickValues(xAxisTicks)
            .tickFormat(d3.format("d"))
            .orient("bottom");
        var yAxis = d3.svg.axis()
            .scale(yScale)
            .orient("left");
        if (maxY - minY < 8) {
            yAxis.ticks(maxY - minY + 1);
        }
        var svg = d3.select(graph_html)
            .attr("width", graphWidth)
            .attr("height", graphHeight)
            .append("g")
            .attr("transform", "translate(" + margin.left + "," + margin.top + ")");
        var bar = svg.selectAll(".bar")
            .data(data)
            .enter().append("g")
            .attr("class", "ob2-graph--bar")
            .attr("transform", function(d) {
                return "translate(" + xScale(d.x) + "," + yScale(d.y) + ")";
            });
        bar.append("rect")
            .attr("x", 1)
            .attr("width", function(d) { return xScale(d.dx - d.x) - 1; })
            .attr("height", function(d) { return innerHeight - yScale(d.y); });
        svg.append("g")
            .attr("class", "ob2-graph--bar-axis")
            .attr("transform", "translate(0," + innerHeight + ")")
            .call(xAxis);
        svg.append("g")
            .attr("class", "ob2-graph--bar-axis")
            .call(yAxis);
    }

    function draw_smooth(graph_html, data) {
        var get_time = function(d) { return d[0]; };
        var get_low = function(d) { return d[1]; };
        var get_high = function(d) { return d[d.length - 1]; };
        var parseDate = d3.time.format("%Y-%m-%dT%H:%M:%S%Z").parse;
        data.forEach(function(d) {
            d[0] = parseDate(d[0]);
        });
        var minX = d3.min(data, get_time);
        var maxX = d3.max(data, get_time);
        var minY = d3.min(data, get_low);
        var maxY = d3.max(data, get_high);
        var graph = $(graph_html);
        var graphWidth = graph.width();
        var graphHeight = graphWidth / parseFloat(graph.data("aspectratio"));
        var margin = {top: 20, right: 10, bottom: 30, left: 30};
        var innerWidth = graphWidth - margin.left - margin.right;
        var innerHeight = graphHeight - margin.top - margin.bottom;
        var xScale = d3.time.scale()
            .domain([minX, maxX])
            .range([0, innerWidth]);
        var yScale = d3.scale.linear()
            .domain([minY, maxY])
            .range([innerHeight, 0]);
        var xAxis = d3.svg.axis()
            .scale(xScale)
            .orient("bottom")
            .ticks(6);
        var yAxis = d3.svg.axis()
            .scale(yScale)
            .orient("left");
        if (maxY - minY < 8) {
            yAxis.ticks(maxY - minY + 1);
        }
        var svg = d3.select(graph_html)
            .attr("width", graphWidth)
            .attr("height", graphHeight)
            .append("g")
            .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

        for (var i = 1; i < data[0].length; i++) {
            (function(i) {
                var line = d3.svg.line()
                    .interpolate("basis")
                    .x(function(d) { return xScale(get_time(d)); })
                    .y(function(d) { return yScale(d[i]); })
                    .defined(function(d) { return d[i] != null; });
                svg.append("path")
                    .datum(data)
                    .attr("class", "ob2-graph--smooth-line")
                    .attr("d", line);
            })(i);
        }
        svg.append("g")
            .attr("class", "ob2-graph--smooth-y-axis")
            .call(yAxis);
        svg.append("g")
            .attr("class", "ob2-graph--smooth-x-axis")
            .attr("transform", "translate(0," + innerHeight + ")")
            .call(xAxis);
    }

    $(".js-ob2-graph").each(function(_, graph) {
        var endpoint = $(graph).data("endpoint");
        $.getJSON(endpoint, function(data) {
            var type = $(graph).data("type");
            if (type == "histogram") {
                draw_histogram(graph, data);
            } else if (type == "smooth") {
                draw_smooth(graph, data);
            }
        });
    });
});
