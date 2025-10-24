-- CreateTable
CREATE TABLE `Objects` (
    `id` VARCHAR(191) NOT NULL,
    `terrainId` VARCHAR(191) NOT NULL,
    `roadId` VARCHAR(191) NULL,
    `userId` VARCHAR(191) NOT NULL,
    `blendFilePath` VARCHAR(191) NOT NULL,
    `previewPath` VARCHAR(191) NOT NULL,
    `glbFilePath` VARCHAR(191) NULL,
    `objectCount` INTEGER NOT NULL,
    `metadata` JSON NULL,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),

    INDEX `Objects_terrainId_idx`(`terrainId`),
    INDEX `Objects_roadId_idx`(`roadId`),
    INDEX `Objects_userId_idx`(`userId`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- AddForeignKey
ALTER TABLE `Objects` ADD CONSTRAINT `Objects_terrainId_fkey` FOREIGN KEY (`terrainId`) REFERENCES `Terrain`(`id`) ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE `Objects` ADD CONSTRAINT `Objects_roadId_fkey` FOREIGN KEY (`roadId`) REFERENCES `Road`(`id`) ON DELETE SET NULL ON UPDATE CASCADE;
