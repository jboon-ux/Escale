"""Tests sans réseau : python -m unittest discover -s tests -v"""
import json
import os
import unittest
from unittest.mock import patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app


class EscaleTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app.app)
        app._hits.clear()

    def test_pages(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get('/api/config').status_code, 200)

    def test_unconfigured_is_safe(self):
        with patch.dict(os.environ, {}, clear=True):
            r = self.client.post('/api/recommend', json={'mode': 'restaurant', 'answers': []})
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()['detail'], 'not_configured')

    def test_bad_mode(self):
        r = self.client.post('/api/recommend', json={'mode': 'unknown', 'answers': []})
        self.assertEqual(r.status_code, 400)

    def test_private_access_code(self):
        with patch.object(app, 'ACCESS_CODE', 'test-only'):
            r = self.client.post('/api/recommend', json={'mode': 'restaurant', 'answers': []})
        self.assertEqual(r.status_code, 401)

    def test_local_rate_limit(self):
        with patch.object(app, 'RATE_LIMIT_PER_HOUR', 1):
            app.check_rate_limit('test')
            with self.assertRaises(HTTPException) as e:
                app.check_rate_limit('test')
        self.assertEqual(e.exception.status_code, 429)

    def test_provider_limit_never_retries_or_falls_back(self):
        with patch('app.httpx.Client') as client:
            client.return_value.__enter__.return_value.post.return_value = httpx.Response(429)
            with self.assertRaises(HTTPException) as e:
                app.provider_post('https://api.groq.com/test', 'test-key', {})
            self.assertEqual(e.exception.status_code, 429)
            self.assertEqual(client.return_value.__enter__.return_value.post.call_count, 1)

    def test_only_sourced_links_survive(self):
        source = {'title': 'Test Bistro Paris 14e', 'url': 'https://example.org/bistro', 'content': 'Test Bistro se trouve à Paris 14e.'}
        data = {'sections': [{'title': 'Restaurants', 'items': [
            {'name': 'Test Bistro', 'url': source['url'], 'evidence': source['title'], 'sources': ['Guide Michelin'], 'distinction': '3 étoiles', 'access': 'oui'},
            {'name': 'Invented', 'url': 'https://wrong.invalid', 'evidence': source['title']}
        ]}], 'tips': [], 'itinerary': []}
        response = {'choices': [{'message': {'content': json.dumps(data)}}]}
        with patch.dict(os.environ, {'GROQ_API_KEY': 'test'}), patch('app.search_web', return_value=[source]), patch('app.provider_post', return_value=response):
            result = app.ask_groq(app.RecommendRequest(mode='restaurant', answers=[app.Answer(label='Lieu', value='Paris 14e')]))
        items = result['sections'][0]['items']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['sources'], [])
        self.assertEqual(items[0]['distinction'], '')
        self.assertEqual(items[0]['access'], 'non vérifié')

    def test_wrong_arrondissement_is_rejected(self):
        source = {'title': 'Bistro Paris 18e', 'url': 'https://example.org/bistro', 'content': 'Paris 18e'}
        data = {'sections': [{'title': 'Restaurants', 'items': [{'name': 'Bistro', 'url': source['url'], 'evidence': source['title']}]}]}
        response = {'choices': [{'message': {'content': json.dumps(data)}}]}
        with patch.dict(os.environ, {'GROQ_API_KEY': 'test'}), patch('app.search_web', return_value=[source]), patch('app.provider_post', return_value=response):
            with self.assertRaises(HTTPException) as e:
                app.ask_groq(app.RecommendRequest(mode='restaurant', answers=[app.Answer(label='Lieu', value='Paris 14e')]))
        self.assertEqual(e.exception.detail, 'no_sources')

    def test_parse_fenced_json(self):
        self.assertEqual(app.parse_json('```json\n{"sections": []}\n```'), {'sections': []})


if __name__ == '__main__':
    unittest.main()
