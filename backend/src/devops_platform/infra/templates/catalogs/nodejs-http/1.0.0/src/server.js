import http from 'node:http';

const server = http.createServer((request, response) => {
  const healthy = request.url === '/healthz';
  response.writeHead(healthy ? 200 : 404, { 'content-type': 'application/json' });
  response.end(JSON.stringify(healthy ? { status: 'ok' } : { error: 'not_found' }));
});
server.listen(Number(process.env.PORT ?? 8080), '0.0.0.0');
