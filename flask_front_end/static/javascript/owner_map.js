// This file controls the interactivity of the Owner Map page,
// including autocomplete feature, creating Google Map, 
// plotting GROW sensors on map, and displaying Owner
// statistics and sensors statistics via created tables.

google.charts.load('current', {'packages':['corechart', 'table']});

var activeWindow;

// Used to clear tables & graphs
function clearBox(elementID)
{
    document.getElementById(elementID).innerHTML = "";
}

// Autocomplete function to detect addresses typed in search box
$(function() {
    $("#autocomplete").autocomplete({
        source:function(request, response) {
            $.getJSON("/autocomplete",{
                q: request.term, // In flask, "q" will be the argument to look for using request.args
            }, function(data) {
                response(data.matching_results); // matching_results from jsonify
            });
        },
        minLength: 2,
    });
})

// Function to add InfoWindow to map marker
function addInfoWindow(marker, message) {
    var infoWindow = new google.maps.InfoWindow({
        content: message
    });

    google.maps.event.addListener(marker, 'click', function() {
        // Close active window if exists
        if (activeWindow != null) {
            activeWindow.close();
        }
        // Open new window 
        infoWindow.open(map, marker); 
        // Store new window in global variable 
        activeWindow = infoWindow; 
    });

    google.maps.event.addListener(marker, 'click', function() {
        // Clear all values in input boxes
        document.getElementById('end_date').value = '';
        document.getElementById('start_date').value = '';
        document.getElementById('sensor_id').value = '';
        document.getElementById('owner_id').value = '';
        var owner_reg = /Owner Id\: (.*)<br>Days/;
        var owner = owner_reg.exec(message)[1];
        document.getElementById('owner_id').value += owner;
        // Match end date & insert to input box
        var reg = /End Date\: (.*)<br>Sensor Id/;
        var end = reg.exec(message)[1];
        document.getElementById('end_date').value += end;
        // Match start date & insert to input box
        // Start date is the GROW start date, unless
        // the range is larger than 9 days, 
        // then the start date = end date minus 9 days.
        var start_reg = /Start Date\: (.*)<br>End Date/;
        var start = start_reg.exec(message)[1];
        var start_date = new Date(start);
        var end_date = new Date(end);
        end_date.setDate(end_date.getDate()-9);
        if (start_date > end_date) {
            var start_date = start_date.toISOString().slice(0,-5);
            document.getElementById('start_date').value += start_date;
        } else {
            var new_start_date = end_date.toISOString().slice(0,-5);
            document.getElementById('start_date').value += new_start_date;
        }
        // Match sensor id & insert to input box
        var sensor_reg = /Sensor Id\: (.*)/;
        var sensor_id = sensor_reg.exec(message)[1];
        document.getElementById('sensor_id').value += sensor_id;
    });
}

// Functions which call Flask backend api endpoint, receives data, 
// then calls the initMap function with that data.
function getSensorData() {
    $.getJSON('http://flask-env.hhxgagpxbh.eu-west-1.elasticbeanstalk.com/api/all_grow_true_json', initMap);
}

function getHealthyData() {
    $.getJSON('http://flask-env.hhxgagpxbh.eu-west-1.elasticbeanstalk.com/api/all_grow_healthy_json', initMap);
}

function getRecoveredData() {
    $.getJSON('http://flask-env.hhxgagpxbh.eu-west-1.elasticbeanstalk.com/api/all_grow_recovered_json', initMap);
}

function getFaultyData() {
    $.getJSON('http://flask-env.hhxgagpxbh.eu-west-1.elasticbeanstalk.com/api/all_grow_faulty_json', initMap);
}

// Fetch all GROW sensors with autocompleted address, plot sensor markers on map
function getGrowByAddress() {
    address = document.getElementById('autocomplete').value; 
    params = {
        address: address, 
    }
    $.getJSON('http://flask-env.hhxgagpxbh.eu-west-1.elasticbeanstalk.com/grow_by_address', params, initMap);
}

// Fetch all GROW sensors with Owner ID, plot sensor markers on map
function getGrowByOwner() {
    owner_id = document.getElementById('owner_id').value; 
    params = {
        owner_id: owner_id, 
    }
    $.getJSON('http://flask-env.hhxgagpxbh.eu-west-1.elasticbeanstalk.com/grow_by_owner', params, initMap);
}

// Queries backend endpoint 'owner_stats,' sends data to tableOwnerStats function
function getOwnerStats() {
    owner_id = document.getElementById('owner_id').value; 
    params = {
        owner_id: owner_id, 
    }
    $.getJSON('http://flask-env.hhxgagpxbh.eu-west-1.elasticbeanstalk.com/owner_stats', params, tableOwnerStats);
}

// Queries backend endpoint 'healthy_stats', sends data to tableHealthyStats
function getHealthySensors() {
    owner_id = document.getElementById('owner_id').value; 
    params = {
        owner_id: owner_id, 
    }
    $.getJSON('http://flask-env.hhxgagpxbh.eu-west-1.elasticbeanstalk.com/healthy_stats', params, tableHealthyStats);
}

// Queries backend endpoint 'recovered_stats', sends data to tableHealthyStats
function getRecoveredSensors() {
    owner_id = document.getElementById('owner_id').value; 
    params = {
        owner_id: owner_id, 
    }
    $.getJSON('http://flask-env.hhxgagpxbh.eu-west-1.elasticbeanstalk.com/recovered_stats', params, tableRecoveredStats);
}

// Queries backend endpoint 'faulty_stats', sends data to tableHealthyStats
function getFaultySensors() {
    owner_id = document.getElementById('owner_id').value; 
    params = {
        owner_id: owner_id, 
    }
    $.getJSON('http://flask-env.hhxgagpxbh.eu-west-1.elasticbeanstalk.com/faulty_stats', params, tableFaultyStats);
}

// Creates table to show Healthy sensor statistics
function tableHealthyStats(stats) {
    var data = new google.visualization.DataTable();
    var cssClassNames = {
        'headerRow': 'italic-darkblue-font large-font bold-font',
        'tableRow': '',
        'oddTableRow': 'beige-background',
        'selectedTableRow': 'orange-background large-font',
        'hoverTableRow': '',
        'headerCell': 'gold-border',
        'tableCell': '',
        'rowNumberCell': 'underline-blue-font'};
    data.addColumn('string', 'Sensor Id');
    data.addColumn('number', 'Battery Level (%)');
    data.addColumn('number', 'Soil Moisture (%)');
    data.addColumn('number', 'Light (mol/m2/d)');
    data.addColumn('number', 'Air Temperature (C)');
    data.addColumn('string', 'Last Upload DateTime');
    for (i = 0; i < stats.length; i++) {
        data.addRow([stats[i][0][0],
            stats[i][0][1],
            stats[i][0][2],
            stats[i][0][3],
            stats[i][0][4],
            stats[i][0][5]
        ]);
    };

    var table = new google.visualization.Table(document.getElementById('healthy_stats_table'));
    table.draw(data, {showRowNumber: true, width: '50%', height: '100%', cssClassNames: cssClassNames});

    // Listens for user to select a row in the table, automatically fills sensor info 
    // boxes with the info the user clicked. Allows user to easily graph data.
    google.visualization.events.addListener(table, 'select', function() {
        var row = table.getSelection()[0].row;
        var sensor_id = data.getValue(row, 0);
        var end_date = new Date(data.getValue(row, 5));
        var start_date = new Date(data.getValue(row, 5));
        start_date.setDate(start_date.getDate()-9);
        var end_date = end_date.toISOString().slice(0,-5);
        var start_date = start_date.toISOString().slice(0,-5);
        document.getElementById('end_date').value = '';
        document.getElementById('start_date').value = '';
        document.getElementById('sensor_id').value = '';
        document.getElementById('start_date').value += start_date;
        document.getElementById('end_date').value += end_date;
        document.getElementById('sensor_id').value += sensor_id;
      });
}

// Creates table to show Recovered sensor statistics
function tableRecoveredStats(stats) {
    var data = new google.visualization.DataTable();
    var cssClassNames = {
        'headerRow': 'italic-darkblue-font large-font bold-font',
        'tableRow': '',
        'oddTableRow': 'beige-background',
        'selectedTableRow': 'orange-background large-font',
        'hoverTableRow': '',
        'headerCell': 'gold-border',
        'tableCell': '',
        'rowNumberCell': 'underline-blue-font'};
    data.addColumn('string', 'Sensor Id');
    data.addColumn('number', 'Battery Level (%)');
    data.addColumn('number', 'Soil Moisture (%)');
    data.addColumn('number', 'Light (mol/m2/d)');
    data.addColumn('number', 'Air Temperature (C)');
    data.addColumn('string', 'Last Upload DateTime');
    for (i = 0; i < stats.length; i++) {
        data.addRow([stats[i][0][0],
            stats[i][0][1],
            stats[i][0][2],
            stats[i][0][3],
            stats[i][0][4],
            stats[i][0][5]
        ]);
    };

    var table = new google.visualization.Table(document.getElementById('recovered_stats_table'));
    table.draw(data, {showRowNumber: true, width: '50%', height: '100%', cssClassNames: cssClassNames});

    // Listens for user to select a row in the table, automatically fills sensor info 
    // boxes with the info the user clicked. Allows user to easily graph data.
    google.visualization.events.addListener(table, 'select', function() {
        var row = table.getSelection()[0].row;
        var sensor_id = data.getValue(row, 0);
        var end_date = new Date(data.getValue(row, 5));
        var start_date = new Date(data.getValue(row, 5));
        start_date.setDate(start_date.getDate()-9);
        var end_date = end_date.toISOString().slice(0,-5);
        var start_date = start_date.toISOString().slice(0,-5);
        document.getElementById('end_date').value = '';
        document.getElementById('start_date').value = '';
        document.getElementById('sensor_id').value = '';
        document.getElementById('start_date').value += start_date;
        document.getElementById('end_date').value += end_date;
        document.getElementById('sensor_id').value += sensor_id;
      });
}

// Creates table to show Faulty sensor statistics
function tableFaultyStats(stats) {
    var data = new google.visualization.DataTable();
    var cssClassNames = {
        'headerRow': 'italic-darkblue-font large-font bold-font',
        'tableRow': '',
        'oddTableRow': 'beige-background',
        'selectedTableRow': 'orange-background large-font',
        'hoverTableRow': '',
        'headerCell': 'gold-border',
        'tableCell': '',
        'rowNumberCell': 'underline-blue-font'};
    data.addColumn('string', 'Sensor Id');
    data.addColumn('number', 'Battery Level (%)');
    data.addColumn('number', 'Soil Moisture (%)');
    data.addColumn('number', 'Light (mol/m2/d)');
    data.addColumn('number', 'Air Temperature (C)');
    data.addColumn('string', 'Last Upload DateTime');
    for (i = 0; i < stats.length; i++) {
        data.addRow([stats[i][0][0],
            stats[i][0][1],
            stats[i][0][2],
            stats[i][0][3],
            stats[i][0][4],
            stats[i][0][5]
        ]);
    };

    var table = new google.visualization.Table(document.getElementById('faulty_stats_table'));
    table.draw(data, {showRowNumber: true, width: '50%', height: '100%', cssClassNames: cssClassNames});

    // Listens for user to select a row in the table, automatically fills sensor info 
    // boxes with the info the user clicked. Allows user to easily graph data.
    google.visualization.events.addListener(table, 'select', function() {
        var row = table.getSelection()[0].row;
        var sensor_id = data.getValue(row, 0);
        var end_date = new Date(data.getValue(row, 5));
        var start_date = new Date(data.getValue(row, 5));
        start_date.setDate(start_date.getDate()-9);
        var end_date = end_date.toISOString().slice(0,-5);
        var start_date = start_date.toISOString().slice(0,-5);
        document.getElementById('end_date').value = '';
        document.getElementById('start_date').value = '';
        document.getElementById('sensor_id').value = '';
        document.getElementById('start_date').value += start_date;
        document.getElementById('end_date').value += end_date;
        document.getElementById('sensor_id').value += sensor_id;

      });
}

// Creates table to show GROW Owner statistics
function tableOwnerStats(stats) {
    var data = new google.visualization.DataTable();
    var cssClassNames = {
        'headerRow': 'italic-darkblue-font large-font bold-font',
        'tableRow': '',
        'oddTableRow': 'beige-background',
        'selectedTableRow': 'orange-background large-font',
        'hoverTableRow': '',
        'headerCell': 'gold-border',
        'tableCell': '',
        'rowNumberCell': 'underline-blue-font'};
    data.addColumn('string', 'Owner Id');
    data.addColumn('number', 'Healthy Sensors');
    data.addColumn('number', 'Recovered Sensors');
    data.addColumn('number', 'Faulty Sensors');
    data.addColumn('number', 'Total Sensors')
    data.addRow([stats['owner_id'],
                stats['healthy'].length,
                stats['recovered'].length,
                stats['faulty'].length,
                stats['healthy'].length + stats['recovered'].length + stats['faulty'].length])

    var table = new google.visualization.Table(document.getElementById('owner_stats_table'));
    table.draw(data, {showRowNumber: true, width: '50%', height: '100%', cssClassNames: cssClassNames});
}

// Queries backend endpoint 'indiv_grow_data', passes data to processGrowData function
function getGrowData() {
    start = document.getElementById('start_date').value; 
    end = document.getElementById('end_date').value; 
    sensor_id = document.getElementById('sensor_id').value;
    params = {
        start: start, 
        end: end, 
        sensor_id: sensor_id
    }
    $.getJSON('http://flask-env.hhxgagpxbh.eu-west-1.elasticbeanstalk.com/api/indiv_grow_data', params, processGrowData);
}

// Queries backend endpoint 'check_faulty_grow', passes data to processGrowFaults
function checkGrowFaults() {
    sensor_id = document.getElementById('sensor_id').value;
    params = {
        sensor_id: sensor_id
    }
    $.getJSON('http://flask-env.hhxgagpxbh.eu-west-1.elasticbeanstalk.com/api/check_faulty_grow', params, processGrowFaults);
}

// Process GROW fault classification data based on days since last anomaly
function processGrowFaults(data) {
    if (data.length == 0) {
        var days_since_anomaly = null;
        var last_anomaly_datetime = null;
    } else {
        var days_since_anomaly = data[0][0];
        var last_anomaly_datetime = data[0][1];
    }

    if (days_since_anomaly == null) {
        var health_status = 'Healthy';
    } else if (days_since_anomaly < 2) {
        var health_status = 'Not Healthy';
    } else {
        var health_status = 'Recovered State';
    }
    document.getElementById('grow_health_status').innerHTML = health_status;
    document.getElementById('grow_anomaly_date').innerHTML = last_anomaly_datetime;
}

// Process GROW data to prepare it for graphing, pass data to drawGrowChart function
function processGrowData(data) {
    // The order of GROW variables returned is not consistent,
    // so we need to check if the variable names match
    // before assigning them to their javascript variables.
    if (data['Data'][0]['VariableCode'] == 'Thingful.Connectors.GROWSensors.air_temperature') {
        air_temperature = data['Data'][0]['Data'];
    } else if (data['Data'][0]['VariableCode'] == 'Thingful.Connectors.GROWSensors.calibrated_soil_moisture') {
        soil_moisture = data['Data'][0]['Data'];
    } else {
        light = data['Data'][0]['Data'];
    }

    if (data['Data'][1]['VariableCode'] == 'Thingful.Connectors.GROWSensors.air_temperature') {
        air_temperature = data['Data'][1]['Data'];
    } else if (data['Data'][1]['VariableCode'] == 'Thingful.Connectors.GROWSensors.calibrated_soil_moisture') {
        soil_moisture = data['Data'][1]['Data'];
    } else {
        light = data['Data'][1]['Data'];
    }

    if (data['Data'][2]['VariableCode'] == 'Thingful.Connectors.GROWSensors.air_temperature') {
        air_temperature = data['Data'][2]['Data'];
    } else if (data['Data'][2]['VariableCode'] == 'Thingful.Connectors.GROWSensors.calibrated_soil_moisture') {
        soil_moisture = data['Data'][2]['Data'];
    } else {
        light = data['Data'][2]['Data'];
    }
    window.grow_air_temperature = air_temperature;
    window.grow_soil_moisture = soil_moisture;
    drawGrowChart(air_temperature, soil_moisture, light);
}

// Queries backend endpoint 'get_wow_data', passes data to processWowData function
function getWowData() {
    start = document.getElementById('start_date').value; 
    end = document.getElementById('end_date').value; 
    sensor_id = document.getElementById('sensor_id').value;
    params = {
        start: start, 
        end: end, 
        sensor_id: sensor_id
    }
    $.getJSON('http://flask-env.hhxgagpxbh.eu-west-1.elasticbeanstalk.com/api/get_wow_data', params, processWowData);
}

// Assigns WOW data to JavaScript variables, passes to three chart/graphing functions
function processWowData(data) {
    distance = data['distance'];
    air_temperature = data['air_temp'];
    datetimes = data['datetime'];
    rainfall = data['rainfall'];
    drawWowChart(distance, air_temperature, datetimes, rainfall);
    drawGrowWowTemp(window.grow_air_temperature, air_temperature, datetimes)
    drawGrowWowRainfall(window.grow_soil_moisture, rainfall, datetimes)
}

// Creates GROW/WOW air temperature comparison chart 
function drawGrowWowTemp(grow_air_temp, wow_air_temp, datetimes) {
    var data = new google.visualization.DataTable();
    data.addColumn('datetime', 'datetime');
    data.addColumn('number', 'grow_air_temp');
    data.addColumn('number', 'wow_air_temp');
    for (i = grow_air_temp.length - 1; i >= 0; i--) {
        var date_str = grow_air_temp[i]['DateTime'];
        var date_edit = date_str.slice(0,4) + '-' 
                        + date_str.slice(4,6) + '-' 
                        + date_str.slice(6,8) + 'T'
                        + date_str.slice(8,10) + ':'
                        + date_str.slice(10,12) + ':'
                        + date_str.slice(12,14) 
        var my_date = new Date(date_edit);
        data.addRow([my_date, 
            grow_air_temp[i]['Value'], 
            null
        ]);
    }
    for (i = wow_air_temp.length - 1; i >= 0; i--) {
        var date_str = datetimes[i];
        var my_date = new Date(date_str);
        data.addRow([my_date,
                    null,
                    wow_air_temp[i]
                ]);
    }
    var options = {
        title: 'GROW/WOW Air Temperature Comparison',
        legend: {position: 'bottom'},
        height: 400,
    };
    var chart = new google.visualization.LineChart(document.getElementById('grow_wow_temp_chart'));
    chart.draw(data, options);
}

// Creates GROW/WOW rainfall/soil moisture comparison chart
function drawGrowWowRainfall(grow_soil_moisture, wow_rainfall, datetimes) {
    var data = new google.visualization.DataTable();
    data.addColumn('datetime', 'datetime');
    data.addColumn('number', 'grow_soil_moisture');
    data.addColumn('number', 'wow_rainfall');
    for (i = grow_soil_moisture.length - 1; i >= 0; i--) {
        var date_str = grow_soil_moisture[i]['DateTime'];
        var date_edit = date_str.slice(0,4) + '-' 
                        + date_str.slice(4,6) + '-' 
                        + date_str.slice(6,8) + 'T'
                        + date_str.slice(8,10) + ':'
                        + date_str.slice(10,12) + ':'
                        + date_str.slice(12,14) 
        var my_date = new Date(date_edit);
        data.addRow([my_date, 
            grow_soil_moisture[i]['Value'], 
            null
        ]);
    }
    for (i = wow_rainfall.length - 1; i >= 0; i--) {
        var date_str = datetimes[i];
        var my_date = new Date(date_str);
        data.addRow([my_date,
                    null,
                    wow_rainfall[i]
                ]);
    }
    var options = {
        title: 'GROW/WOW Rainfall - Soil Moisture Comparison',
        legend: {position: 'bottom'},
        height: 400,
    };
    var chart = new google.visualization.LineChart(document.getElementById('grow_wow_rainfall_chart'));
    chart.draw(data, options);
}

// Creates chart that shows all 3 GROW data variables
function drawGrowChart(air_temperature, soil_moisture, light) {
    var data = new google.visualization.DataTable();
    data.addColumn('datetime', 'datetime');
    data.addColumn('number', 'air_temp');
    data.addColumn('number', 'soil_moisture');
    data.addColumn('number', 'light');
    // Iterates through array backwards to graph data
    // from past to recent
    for (i = air_temperature.length - 1; i >= 0; i--) {
        var date_str = air_temperature[i]['DateTime'];
        var date_edit = date_str.slice(0,4) + '-' 
                        + date_str.slice(4,6) + '-' 
                        + date_str.slice(6,8) + 'T'
                        + date_str.slice(8,10) + ':'
                        + date_str.slice(10,12) + ':'
                        + date_str.slice(12,14) 
        var my_date = new Date(date_edit);
        data.addRow([my_date, 
                    air_temperature[i]['Value'],
                    soil_moisture[i]['Value'],
                    light[i]['Value']
                ]);
    }
    var options = {
        title: 'GROW Sensor Values',
        legend: {position: 'bottom'},
        height: 400,
        backgroundColor: '#ffffff'
    };
    var chart = new google.visualization.LineChart(document.getElementById('grow_line_chart'));
    chart.draw(data, options);
}

// Creates chart that shows both WOW variables
function drawWowChart(distance, air_temperature, datetimes, rainfall) {
    var data = new google.visualization.DataTable();
    data.addColumn('datetime', 'datetime');
    data.addColumn('number', 'air_temp');
    data.addColumn('number', 'rainfall');
    for (i = air_temperature.length - 1; i >= 0; i--) {
        var date_str = datetimes[i];
        var my_date = new Date(date_str);
        data.addRow([my_date,
                    air_temperature[i], 
                    rainfall[i],
                ]);
    }
    var options = {
        title: 'WOW Site ' + distance + ' km away',
        legend: {position: 'bottom'},
        height: 400,
    };
    var chart = new google.visualization.LineChart(document.getElementById('wow_line_chart'));
    chart.draw(data, options);
}

// Creates Google Maps map and plots GROW sensor markers on map
function initMap(data) {
    // Create the map centered on the United Kingdom.
    var map = new google.maps.Map(document.getElementById('map'), {
        zoom: 4,
        center: {lat: 55.3781, lng: 3.4360},
        mapTypeId: 'terrain'
    });

    // Image to use for map pinpoint icon
    var image = {
        url: 'static/images/google-maps-location-icon.jpg',
        scaledSize : new google.maps.Size(12, 12),
    };

    var grow;
    grow = data;
    for (var sensor in grow) {
        var growCircle = new google.maps.Circle({
            strokeColor: '#FF0000',
            strokeOpacity: 0.8,
            strokeWeight: 2,
            fillColor: '#FF0000',
            fillOpacity: 0.35,
            map: map,
            center: new google.maps.LatLng(grow[sensor].latitude, grow[sensor].longitude),
            radius: 200,
            label: grow[sensor].sensor_id,
            county: grow[sensor].address
        });

        var marker = new google.maps.Marker({
            position: new google.maps.LatLng(grow[sensor].latitude, grow[sensor].longitude),
            map: map, 
            animation: google.maps.Animation.DROP,
            icon: image
            });
        
        // Adds Info Window to show info when GROW sensor is clicked
        addInfoWindow(marker, ('Address: ' + grow[sensor].address +
            '<br>Owner Id: ' + grow[sensor].owner_id +
            '<br>Days Active: ' + grow[sensor].days_active +
            '<br>Start Date: ' + grow[sensor].start_date +
            '<br>End Date: ' + grow[sensor].end_date +
            '<br>Sensor Id: ' + grow[sensor].sensor_id));
    }
}

// References:
// Google Maps API Documentation was referenced.
// https://developers.google.com/maps/documentation/javascript/tutorial

// JQuery Reference.
// https://api.jquery.com/jquery.getjson/ 
// JQuery Download.
// https://jquery.com/download/

// Image for Map Marker Icon:
// http://chittagongit.com//images/google-maps-location-icon/google-maps-location-icon-2.jpg

// Anthony Delivanis

