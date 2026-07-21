import pygame

from primiengine import Log, Assets, Render, Actors, Collision
from player import Player


def main():

    pygame.init()
    
    screen = pygame.display.set_mode(
        (800, 600)
    )

    Render.init(screen)
    Actors.init()

    log = Log.get("main")
    Log.disable_console()

    log.info("Engine starting")

    # Load immediately (blocking)
    Assets.load(
        "player",
        "assets/player.png"
    )
    Actors.spawn(
        Player,
        texture=Assets.get("player"),
        position=(200, 300),
        speed= 200
    )
    Actors.spawn(
        Player,
        texture=Assets.get("player"),
        position=(400, 300),
        speed=-100
    )
    Actors.spawn(
        Player,
        texture=Assets.get("player"),
        position=(100, 300),
        speed= 100
    )
    Actors.spawn(
        Player,
        texture=Assets.get("player"),
        position=(100, 100),
        speed=-100
    )

    clock = pygame.time.Clock()

    running = True

    while running:

        dt = clock.tick(60)

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False

        Assets.update()
        Actors.update(dt)
        Collision.update()

        Render.present()
    Actors.close()
    Render.close()
    Log.close()


if __name__ == "__main__":
    main()
