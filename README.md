# EvidenceCast AI

EvidenceCast AI converts approved research findings into traceable multimedia communication assets, including evidence cards, infographics, narration and short videos. Every generated asset is stored with provenance metadata in Backblaze B2 through Genblaze.

## Hackathon

This repository is being developed for the Backblaze Generative Media Hackathon: Build with Genblaze on B2.

## Core workflow

```text
Upload trusted evidence
        ↓
Approve evidence claims
        ↓
Generate a structured media plan
        ↓
Generate images, narration and video
        ↓
Validate claims and media quality
        ↓
Store assets and provenance in Backblaze B2
        ↓
Review, revise and publish
```

## Day 1 objective

The first vertical slice generates one image with Genblaze, persists the image and its provenance manifest to a private Backblaze B2 bucket, and confirms that `Manifest.verify()` succeeds.

## Security

Do not commit API keys, B2 application keys, bucket credentials or populated `.env` files. Use the provided `.env.example` as a template and store real credentials only in a local `.env` file or a secure deployment secret manager.

## Repository status

Initial implementation in progress.
