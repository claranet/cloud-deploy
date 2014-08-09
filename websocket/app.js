app = require('express.io')()
Tail = require('./tail').Tail;

LOG_PATH = "./"
//LOG_PATH="/var/log/ghost/"

app.http().io()

function sanitize_job(job_id) {
    return true;
}

// Setup the ready route, join room and broadcast to room.
app.io.route('ready', function(req) {
    job_id = req.data
    if (sanitize_job(job_id)) {
        try {
            tail = new Tail(LOG_PATH + job_id, '\n', true);    // file to stream
            tail.on('line', function(data) {         // send to client 
                return req.io.emit('new-data', {
                    channel: 'stdout',
                       value: data
                });
            });
        }
        catch (err) {
            return req.io.emit('new-data', {
                channel: 'stderr',
                   value: err.message
            });
        }
    }
    /* req.io.room(req.data).broadcast('announce', {
        message: 'New client in the ' + req.data + ' room. '
    }) */
})

// Send the client html.
app.get('/', function(req, res) {
    res.sendfile(__dirname + '/client.html')
})

app.listen(7076)
