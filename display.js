var max_pixel_sz = 200;
var tries = 0;

function connect(){

	try {
    		var s = new WebSocket("ws://%(HTTP_HOST)s/data");
	}

	catch (e){
		$("#message").html("websocket has a migraine...");
		$("#message_wrapper").textfill({ maxFontPixels: max_pixel_sz });

		console.log("failed to connect to websocket");
		console.log(e);
		return;
	}

	s.onopen = function(e){ 
		tries = 0;
	};

	s.onerror = function(e){
    	      console.log("got a websocket error!");
	      console.log(e);
	};

	s.onclose = function(e){

		console.log("websocket go boom...");

		if (tries > 10){

			$("#message").html("websocket go boom!");
			$("#message_wrapper").textfill({ maxFontPixels: max_pixel_sz });

			console.log("giving up");
			return;
		}

		tries = tries + 1;
		var delay = 5000 * tries;
		console.log("will try to reconnect in " + delay / 1000 + " seconds");

		setTimeout(function(){
			console.log("trying to reconnect...");
			connect();
		}, delay);
    };

    s.onmessage = function(e) {

	try {
		var rsp = JSON.parse(e.data);

		var now = new Date();

		if (rsp.noop){

			console.log("got a no-op (" + rsp.reason + ") at " + now);

			$("#message").html("panda tickles unicorn");
			$("#message_wrapper").textfill({ maxFontPixels: max_pixel_sz });
		}

		else {

			console.log("got an update at " + now);

			var h = window.innerHeight - 6;
			var w = window.innerWidth - 6;

			var photoid = rsp.photo_id.replace("tag:flickr.com,2005:/photo/", "");
			var href = "http://www.flickr.com/photo.gne?id=" + photoid;

			var img = "<img id=\"photo\" src=\"" + rsp.photo_url + "\" height=\"" + h + "\" width=\"" + w + "\" />";
			var html = "<a href=\"" + href + "\" target=\"_flickr\">" + img + "</a>";

			// TO DO: fancy image transitions

			$("#photo_wrapper").html(html);

			$('#message').html(rsp.title);
			$("#message_wrapper").textfill({ maxFontPixels: max_pixel_sz });
		}
	}

	catch (err){
		console.log(err);
	}

    }
}

function resize(){

	var ph = $("#photo");
	if (! ph){ return; }

	var h = window.innerHeight - 6;
	var w = window.innerWidth - 6;

	ph.attr("height", h);
	ph.attr("width", w);

	assign_wrapper_dimensions();
}

function assign_wrapper_dimensions(){
	var h = window.innerHeight;
	var w = window.innerWidth;

	$("#message_wrapper").css("max-width", (w * .95) + 'px');
	$("#message_wrapper").css("max-height", (h * .90) + 'px');
	$("#message_wrapper").textfill({ maxFontPixels: max_pixel_sz });
}

window.onload = function(){
	assign_wrapper_dimensions();
	connect();
}

window.onresize = function(){
	resize();
}
