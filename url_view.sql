CREATE VIEW content_urls AS SELECT id, posts.user, service, unnest(regexp_matches(content, 'https?://(?:[-a-zA-Z0-9_~]+\.)+[-a-zA-Z0-9_~]+(?:/[-a-zA-Z0-9_~%\.]+)+(?:\?[-a-zA-Z0-9_~%\.&=]+)?(?:#[-a-zA-Z0-9_~%\.&=]+)?', 'g')) as match FROM posts ORDER BY posts.user, id;

